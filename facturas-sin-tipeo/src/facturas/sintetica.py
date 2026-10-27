"""Generador de facturas SINTÉTICAS para tests y para la demo.

No reemplaza a los datos reales: sirve para probar el circuito completo
(QR -> extracción -> reglas -> evaluación) sin exponer documentos de nadie.
Cada PDF lleva la leyenda "DOCUMENTO SINTÉTICO - SIN VALIDEZ FISCAL" y los
resultados que se obtengan con estos archivos no se reportan como métricas.
"""

from __future__ import annotations

import base64
import io
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pymupdf as fitz

from .arca import describir_comprobante, digito_verificador_cuit, letra_comprobante
from .modelos import AlicuotaIVA, FacturaExtraida, Item

LEYENDA = "DOCUMENTO SINTÉTICO - SIN VALIDEZ FISCAL"

_PRODUCTOS = [
    ("Servicio de conectividad mensual", 18500.0),
    ("Resma papel A4 75g", 7800.0),
    ("Mantenimiento preventivo equipo", 42000.0),
    ("Cartucho tóner compatible", 23990.0),
    ("Abono soporte técnico", 65000.0),
    ("Flete y distribución", 12400.0),
]


@dataclass
class FacturaSintetica:
    ruta: Path
    verdad: FacturaExtraida
    url_qr: str


def formato_ar(valor: float) -> str:
    """1234.5 -> '1.234,50' (formato argentino)."""
    return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def cuit_aleatorio(rng: random.Random, prefijo: str = "30") -> str:
    while True:
        base = prefijo + "".join(str(rng.randint(0, 9)) for _ in range(8))
        dv = digito_verificador_cuit(base)
        if dv is not None:
            return base + str(dv)


def url_qr(f: FacturaExtraida) -> str:
    datos = {
        "ver": 1,
        "fecha": f.fecha_emision,
        "cuit": int(f.emisor_cuit),
        "ptoVta": f.punto_venta,
        "tipoCmp": f.tipo_comprobante,
        "nroCmp": f.numero,
        "importe": f.importe_total,
        "moneda": f.moneda,
        "ctz": f.tipo_cambio or 1,
        "tipoDocRec": f.receptor_tipo_doc,
        "nroDocRec": int(f.receptor_nro_doc or 0),
        "tipoCodAut": "E",
        "codAut": int(f.cae) if f.cae else None,
    }
    carga = base64.b64encode(json.dumps(datos, separators=(",", ":")).encode()).decode()
    return f"https://www.afip.gob.ar/fe/qr/?p={carga}"


def generar_verdad(rng: random.Random, tipo: int, hoy: date) -> FacturaExtraida:
    letra = letra_comprobante(tipo)
    items = []
    for descripcion, precio in rng.sample(_PRODUCTOS, rng.randint(1, 3)):
        cantidad = float(rng.randint(1, 4))
        items.append(Item(descripcion=descripcion, cantidad=cantidad, precio_unitario=precio,
                          subtotal=round(cantidad * precio, 2)))
    neto = round(sum(i.subtotal for i in items), 2)
    fecha = hoy - timedelta(days=rng.randint(1, 60))

    # La "verdad" registra solo lo que el PDF imprime, con las mismas reglas que
    # se le piden al modelo: el neto de un B o un C no figura, así que va en None.
    if letra == "A":
        receptor_tipo, receptor_nro = 80, cuit_aleatorio(rng, "30")
        iva = [AlicuotaIVA(alicuota=21.0, importe=round(neto * 0.21, 2))]
        otros = round(neto * 0.03, 2) if rng.random() < 0.5 else None
        total = round(neto + iva[0].importe + (otros or 0), 2)
        netos = dict(importe_neto_gravado=neto)
    elif letra == "B":
        receptor_tipo, receptor_nro = 96, str(rng.randint(20_000_000, 45_000_000))
        # Precios finales con IVA incluido; se informa el IVA contenido.
        iva = [AlicuotaIVA(alicuota=21.0, importe=round(neto - neto / 1.21, 2))]
        otros, total, netos = None, neto, {}
    else:
        receptor_tipo, receptor_nro = 80, cuit_aleatorio(rng, "20")
        iva, otros, total, netos = [], None, neto, {}

    return FacturaExtraida(
        emisor_cuit=cuit_aleatorio(rng, "30"),
        emisor_razon_social=rng.choice(["Distribuidora Demo S.A.", "Servicios Ficticios SRL", "Insumos Ejemplo SAS"]),
        tipo_comprobante=tipo,
        punto_venta=rng.randint(1, 30),
        numero=rng.randint(1, 99_999),
        fecha_emision=fecha.isoformat(),
        receptor_tipo_doc=receptor_tipo,
        receptor_nro_doc=receptor_nro,
        moneda="PES",
        tipo_cambio=1.0,
        iva=iva,
        otros_tributos=otros,
        importe_total=total,
        cae="7" + "".join(str(rng.randint(0, 9)) for _ in range(13)),  # los CAE reales empiezan con 7
        cae_vencimiento=(fecha + timedelta(days=10)).isoformat(),
        items=items,
        **netos,
    )


def _png_qr(texto: str) -> bytes:
    import qrcode  # dependencia de desarrollo: solo hace falta para generar sintéticas

    buffer = io.BytesIO()
    qrcode.make(texto, box_size=6, border=2).save(buffer, format="PNG")
    return buffer.getvalue()


def dibujar_pdf(f: FacturaExtraida, ruta: Path, qr: str | None) -> None:
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)  # A4
    y = 40

    def linea(texto: str, x: float = 40, tam: float = 10, color=(0, 0, 0)) -> None:
        nonlocal y
        pagina.insert_text((x, y), texto, fontsize=tam, color=color)
        y += tam + 6

    linea(LEYENDA, tam=12, color=(0.8, 0, 0))
    linea(f"{describir_comprobante(f.tipo_comprobante).upper()}   COD. {f.tipo_comprobante:02d}", tam=14)
    linea(f"{f.emisor_razon_social}")
    linea(f"CUIT: {f.emisor_cuit[:2]}-{f.emisor_cuit[2:10]}-{f.emisor_cuit[10]}")
    linea(f"Punto de Venta: {f.punto_venta:05d}   Comp. Nro: {f.numero:08d}")
    fecha = date.fromisoformat(f.fecha_emision)
    linea(f"Fecha de Emisión: {fecha:%d/%m/%Y}")
    linea(f"Receptor - Doc. ({f.receptor_tipo_doc}): {f.receptor_nro_doc}")
    y += 10
    linea("Cant.   Descripción                                   P. Unit.        Subtotal")
    for item in f.items:
        linea(f"{item.cantidad:>4.0f}    {item.descripcion:<44}  {formato_ar(item.precio_unitario):>12}  "
              f"{formato_ar(item.subtotal):>12}")
    y += 10
    if f.iva and letra_comprobante(f.tipo_comprobante) == "A":
        linea(f"Importe Neto Gravado: $ {formato_ar(f.importe_neto_gravado)}")
        for a in f.iva:
            linea(f"IVA {formato_ar(a.alicuota).rstrip('0').rstrip(',')}%: $ {formato_ar(a.importe)}")
    elif f.iva:
        linea(f"Subtotal: $ {formato_ar(f.importe_total)}")
        linea(f"IVA Contenido: $ {formato_ar(f.iva[0].importe)}")
    else:
        linea(f"Subtotal: $ {formato_ar(f.importe_total)}")
    if f.otros_tributos:
        linea(f"Percepción IIBB: $ {formato_ar(f.otros_tributos)}")
    linea(f"Importe Total: $ {formato_ar(f.importe_total)}", tam=12)
    y += 10
    linea(f"CAE N°: {f.cae}   Fecha de Vto. de CAE: {date.fromisoformat(f.cae_vencimiento):%d/%m/%Y}")
    if qr:
        pagina.insert_image(fitz.Rect(40, y + 10, 160, y + 130), stream=_png_qr(qr))
    doc.save(ruta, no_new_id=True)
    doc.close()


def generar_lote(destino: str | Path, n: int, semilla: int = 7, hoy: date | None = None,
                 sin_qr: int = 0, tipos: tuple[int, ...] = (1, 6, 11, 1)) -> list[FacturaSintetica]:
    """Genera `n` facturas en `destino`, rotando los tipos de comprobante (por
    defecto la mitad A, un cuarto B y un cuarto C). Las últimas `sin_qr` salen
    sin QR, para probar el camino de documentos que no se pueden verificar."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    rng = random.Random(semilla)
    hoy = hoy or date.today()
    lote = []
    for i in range(n):
        verdad = generar_verdad(rng, tipos[i % len(tipos)], hoy)
        url = url_qr(verdad)
        ruta = destino / f"sintetica_{i:03d}.pdf"
        dibujar_pdf(verdad, ruta, url if i < n - sin_qr else None)
        lote.append(FacturaSintetica(ruta=ruta, verdad=verdad, url_qr=url))
    return lote
