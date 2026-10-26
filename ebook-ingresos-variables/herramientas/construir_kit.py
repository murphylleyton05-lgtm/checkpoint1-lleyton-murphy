#!/usr/bin/env python3
"""Construye el PDF del kit comercial (comercial/partes/*.html).

Mismo proceso que el ebook: numeración de fuentes por orden de aparición,
índice con números de página, portada, marcadores y metadatos.
Uso: python3 herramientas/construir_kit.py
"""
import re
import subprocess
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from construir_ebook import Marcas, normalizar

RAIZ = Path(__file__).resolve().parent.parent
COM = RAIZ / "comercial"
PARTES = COM / "partes"
TMP = RAIZ / ".construccion"
SALIDA = RAIZ / "entregables" / "Kit-comercial-y-plan-de-lanzamiento.pdf"
RENDER = RAIZ / "herramientas" / "render.cjs"
PIE = "Kit comercial · Ingresos variables, sueldo fijo"


def renumerar_fuentes():
    """Ordena las fuentes kref-N según su primera cita y actualiza las citas."""
    archivos = sorted(PARTES.glob("*.html"))
    lista = next(f for f in archivos if 'class="referencias"' in f.read_text(encoding="utf-8"))
    orden = []
    for f in archivos:
        texto = f.read_text(encoding="utf-8")
        if f == lista:
            texto = texto.split('<ol class="referencias">')[0]
        for m in re.finditer(r'href="#kref-(\d+)"', texto):
            n = int(m.group(1))
            if n not in orden:
                orden.append(n)
    rt = lista.read_text(encoding="utf-8")
    definidas = [int(x) for x in re.findall(r'<li id="kref-(\d+)">', rt)]
    faltan = [n for n in orden if n not in definidas]
    assert not faltan, f"Fuentes citadas sin definir: {faltan}"
    for n in definidas:
        if n not in orden:
            orden.append(n)  # fuentes listadas sin cita: van al final
    mapa = {viejo: nuevo for nuevo, viejo in enumerate(orden, start=1)}
    for f in archivos:
        s = f.read_text(encoding="utf-8")
        s2 = re.sub(r'<a href="#kref-(\d+)">\d+</a>', lambda m: f'<a href="#kref-X{mapa[int(m.group(1))]}">{mapa[int(m.group(1))]}</a>', s).replace("#kref-X", "#kref-")
        if s2 != s:
            f.write_text(s2, encoding="utf-8")
    rt = lista.read_text(encoding="utf-8")
    items = {int(m.group(1)): m.group(0) for m in re.finditer(r'<li id="kref-(\d+)">.*?</li>', rt, flags=re.S)}
    bloque = "\n".join("    " + items[v].replace(f'<li id="kref-{v}">', f'<li id="kref-{mapa[v]}">') for v in orden)
    rt = re.sub(r'(<ol class="referencias">\n).*?(\n  </ol>)', lambda m: m.group(1) + bloque + m.group(2), rt, flags=re.S)
    lista.write_text(rt, encoding="utf-8")


def ensamblar(mapa):
    cuerpo = "\n".join(f.read_text(encoding="utf-8") for f in sorted(PARTES.glob("*.html")))
    cuerpo = re.sub(r'<span class="p" data-pagina="([^"]+)">[^<]*</span>',
                    lambda m: f'<span class="p" data-pagina="{m.group(1)}">{mapa.get(m.group(1), "")}</span>', cuerpo)
    html = ('<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Kit comercial y plan de lanzamiento</title>'
            '<link rel="stylesheet" href="../fuente/estilos.css"></head><body>' + cuerpo + "</body></html>")
    destino = COM / "_kit.html"
    destino.write_text(html, encoding="utf-8")
    return destino


def buscar(pdf, marcas):
    lector = PdfReader(str(pdf))
    textos = [normalizar(p.extract_text() or "") for p in lector.pages]
    inicio = next((i + 1 for i, t in enumerate(textos[:6]) if "contenido" in t and "resumen ejecutivo" in t), 0)
    mapa = {}
    for m in marcas:
        obj = normalizar(m["marca"])
        for i in range(inicio, len(textos)):
            if obj in textos[i]:
                mapa[m["id"]] = i + 1
                break
        else:
            print("  ! No se encontró:", m["marca"])
    return mapa, len(lector.pages)


def main():
    TMP.mkdir(exist_ok=True)
    renumerar_fuentes()
    parser = Marcas()
    for f in sorted(PARTES.glob("*.html")):
        parser.feed(f.read_text(encoding="utf-8"))
    cuerpo_pdf = TMP / "kit-cuerpo.pdf"
    mapa = {}
    for vuelta in range(1, 5):
        html = ensamblar(mapa)
        subprocess.run(["node", str(RENDER), str(html), str(cuerpo_pdf), "--pie", PIE], check=True, capture_output=True)
        nuevo, paginas = buscar(cuerpo_pdf, parser.marcas)
        print(f"Vuelta {vuelta}: {paginas} páginas; {len(nuevo)}/{len(parser.marcas)} secciones")
        if nuevo == mapa:
            break
        mapa = nuevo
    portada_pdf = TMP / "kit-portada.pdf"
    subprocess.run(["node", str(RENDER), str(COM / "portada-kit.html"), str(portada_pdf), "--portada"], check=True, capture_output=True)
    w = PdfWriter()
    w.append(str(portada_pdf))
    w.append(str(cuerpo_pdf))
    w.add_outline_item("Portada", 0)
    for m in parser.marcas:
        if m["id"] in mapa:
            w.add_outline_item(m["titulo"], mapa[m["id"]])
    w.add_metadata({"/Title": "Kit comercial y plan de lanzamiento · Ingresos variables, sueldo fijo", "/Author": "Lleyton Murphy"})
    w.page_mode = "/UseOutlines"
    with open(SALIDA, "wb") as fh:
        w.write(fh)
    print("Listo:", SALIDA, len(PdfReader(str(SALIDA)).pages), "páginas")


if __name__ == "__main__":
    main()
