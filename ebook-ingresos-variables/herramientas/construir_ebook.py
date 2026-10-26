#!/usr/bin/env python3
"""Construye el PDF final del ebook.

Pasos:
  1. Une fuente/partes/*.html (en orden alfabético) dentro de una plantilla.
  2. Renderiza el cuerpo a PDF con Chromium (render.cjs).
  3. Detecta en qué página empieza cada sección (atributo data-marca) y
     completa los números de página del índice. Repite hasta que se estabiliza.
  4. Renderiza la portada, une portada + cuerpo, agrega marcadores y metadatos.

Uso:  python3 herramientas/construir_ebook.py
"""
import json
import re
import subprocess
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader, PdfWriter

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "fuente"
PARTES = FUENTE / "partes"
TMP = RAIZ / ".construccion"
SALIDA = RAIZ / "entregables" / "Ingresos-variables-sueldo-fijo.pdf"
RENDER = RAIZ / "herramientas" / "render.cjs"

TITULO = "Ingresos variables, sueldo fijo"
SUBTITULO = ("El sistema paso a paso para que freelancers e independientes se paguen "
             "un sueldo estable, reserven sus impuestos y dejen de vivir de cobro en cobro")
AUTOR = "Lleyton Murphy"
PIE = "Ingresos variables, sueldo fijo"

PLANTILLA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{titulo}</title>
<link rel="stylesheet" href="estilos.css">
</head>
<body>
{cuerpo}
</body>
</html>
"""


class Marcas(HTMLParser):
    """Recoge (id, data-marca, data-titulo, data-nivel) de las secciones."""

    def __init__(self):
        super().__init__()
        self.marcas = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "data-marca" in a and "id" in a:
            self.marcas.append({
                "id": a["id"],
                "marca": a["data-marca"],
                "titulo": a.get("data-titulo", a["data-marca"]),
                "nivel": int(a.get("data-nivel", "0")),
            })


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    t = t.replace("­", "")              # guiones blandos
    t = re.sub(r"-\s*\n\s*", "", t)            # cortes de palabra
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def ensamblar(mapa: dict) -> Path:
    piezas = []
    for f in sorted(PARTES.glob("*.html")):
        piezas.append(f"<!-- {f.name} -->\n" + f.read_text(encoding="utf-8"))
    cuerpo = "\n".join(piezas)

    def poner(m):
        destino = m.group(1)
        n = mapa.get(destino, "")
        return f'<span class="p" data-pagina="{destino}">{n}</span>'

    cuerpo = re.sub(r'<span class="p" data-pagina="([^"]+)">[^<]*</span>', poner, cuerpo)
    # Gráficos SVG en línea: <!--SVG:nombre-->
    cuerpo = re.sub(r"<!--SVG:([\w-]+)-->",
                    lambda m: (FUENTE / "graficos" / f"{m.group(1)}.svg").read_text(encoding="utf-8"),
                    cuerpo)
    html = PLANTILLA.format(titulo=TITULO, cuerpo=cuerpo)
    destino = FUENTE / "_libro.html"
    destino.write_text(html, encoding="utf-8")
    return destino


def render(html: Path, pdf: Path, portada=False):
    cmd = ["node", str(RENDER), str(html), str(pdf)]
    if portada:
        cmd.append("--portada")
    else:
        cmd += ["--pie", PIE]
    subprocess.run(cmd, check=True)


def buscar_paginas(pdf: Path, marcas: list) -> dict:
    lector = PdfReader(str(pdf))
    textos = [normalizar(p.extract_text() or "") for p in lector.pages]
    # El índice ocupa las primeras páginas: se busca a partir de la última
    # página que contiene la palabra "índice" como encabezado.
    inicio = 0
    for i, t in enumerate(textos[:8]):
        if "contenido" in t and "parte i" in t:
            inicio = i + 1
    mapa = {}
    for m in marcas:
        objetivo = normalizar(m["marca"])
        encontrado = None
        for i in range(inicio, len(textos)):
            if objetivo in textos[i]:
                encontrado = i + 1
                break
        if encontrado is None:
            print(f"  ! No se encontró la marca: {m['marca']!r}", file=sys.stderr)
        else:
            mapa[m["id"]] = encontrado
    return mapa, len(lector.pages)


def main():
    TMP.mkdir(exist_ok=True)
    SALIDA.parent.mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(RAIZ / "herramientas" / "graficos.py")], check=True)

    parser = Marcas()
    for f in sorted(PARTES.glob("*.html")):
        parser.feed(f.read_text(encoding="utf-8"))
    marcas = parser.marcas

    cuerpo_pdf = TMP / "cuerpo.pdf"
    mapa = {}
    for vuelta in range(1, 5):
        html = ensamblar(mapa)
        render(html, cuerpo_pdf)
        nuevo, paginas = buscar_paginas(cuerpo_pdf, marcas)
        print(f"Vuelta {vuelta}: {paginas} páginas; {len(nuevo)}/{len(marcas)} secciones ubicadas")
        if nuevo == mapa:
            break
        mapa = nuevo

    (TMP / "mapa-paginas.json").write_text(json.dumps(mapa, indent=2, ensure_ascii=False))

    portada_pdf = TMP / "portada.pdf"
    render(FUENTE / "portada.html", portada_pdf, portada=True)

    escritor = PdfWriter()
    escritor.append(str(portada_pdf))
    escritor.append(str(cuerpo_pdf))

    # Marcadores (offset +1 por la portada)
    padres = {}
    escritor.add_outline_item("Portada", 0)
    for m in marcas:
        if m["id"] not in mapa:
            continue
        pagina = mapa[m["id"]]  # 1-based dentro del cuerpo => índice = pagina (portada en 0)
        padre = padres.get(m["nivel"] - 1) if m["nivel"] > 0 else None
        item = escritor.add_outline_item(m["titulo"], pagina, parent=padre)
        padres[m["nivel"]] = item

    escritor.add_metadata({
        "/Title": f"{TITULO}: {SUBTITULO}",
        "/Author": AUTOR,
        "/Subject": "Finanzas personales para freelancers e independientes con ingresos variables",
        "/Keywords": "ingresos variables, freelancers, independientes, autónomos, presupuesto, impuestos, fondo de emergencia, Método Embalse",
        "/Creator": "Chromium + pypdf",
    })
    escritor.page_mode = "/UseOutlines"
    with open(SALIDA, "wb") as fh:
        escritor.write(fh)
    total = len(PdfReader(str(SALIDA)).pages)
    print(f"Listo: {SALIDA} ({total} páginas)")


if __name__ == "__main__":
    main()
