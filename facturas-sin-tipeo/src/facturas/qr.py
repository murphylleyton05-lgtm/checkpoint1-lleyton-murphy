"""Lectura del QR fiscal de comprobantes electrónicos (RG 4892).

El QR codifica una URL del tipo https://www.afip.gob.ar/fe/qr/?p=<base64> cuyo
parámetro `p` es un JSON con los datos del comprobante (cuit, ptoVta, tipoCmp,
nroCmp, importe, moneda, ctz, tipoDocRec, nroDocRec, tipoCodAut, codAut...).

En facturas reales aparecen tres problemas que este módulo tolera:
números que vienen como texto ("13649.43"), campos faltantes (QR sin fecha) y
JSON cortado. Cuando el JSON está cortado se descarta el último campo, porque
puede estar truncado ("tipoDocRec": 8 en vez de 80), y se marca `reparado`.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import cv2
import pymupdf as fitz
import numpy as np

from .arca import solo_digitos
from .modelos import DatosQR

_DOMINIOS = ("afip.gob.ar", "arca.gob.ar")
_RUTA_QR = re.compile(r"/fe/qr/?$")


class QRInvalido(ValueError):
    pass


def es_url_fiscal(texto: str) -> bool:
    try:
        url = urlparse(texto.strip())
    except ValueError:
        return False
    dominio_ok = any(url.netloc == d or url.netloc.endswith("." + d) for d in _DOMINIOS)
    return dominio_ok and bool(_RUTA_QR.search(url.path)) and "p=" in url.query


def _b64_a_texto(dato: str) -> str:
    dato = unquote(dato).strip().replace("-", "+").replace("_", "/").replace(" ", "+")
    dato += "=" * (-len(dato) % 4)
    try:
        crudo = base64.b64decode(dato)
    except binascii.Error as exc:
        raise QRInvalido(f"base64 inválido: {exc}") from exc
    return crudo.decode("utf-8", errors="ignore")


def _parsear_json(texto: str) -> tuple[dict, bool]:
    texto = texto.strip()
    try:
        return json.loads(texto), False
    except json.JSONDecodeError:
        pass
    # JSON cortado: retroceder hasta la última coma de primer nivel y cerrar.
    cuerpo = texto.rstrip("}").rstrip()
    while "," in cuerpo:
        cuerpo = cuerpo[: cuerpo.rfind(",")]
        try:
            return json.loads(cuerpo + "}"), True
        except json.JSONDecodeError:
            continue
    raise QRInvalido("el JSON del QR no se pudo leer ni reparar")


def _entero(valor: object) -> int | None:
    if valor in (None, ""):
        return None
    try:
        return int(float(str(valor)))
    except ValueError:
        return None


def _decimal(valor: object) -> float | None:
    if valor in (None, ""):
        return None
    try:
        return float(str(valor))
    except ValueError:
        return None


def normalizar(datos: dict, *, reparado: bool = False, url: str = "") -> DatosQR:
    def digitos(clave: str) -> str | None:
        valor = solo_digitos(datos.get(clave))
        # Un consumidor final sin identificar viaja como nroDocRec 0: no es un documento.
        return valor if valor.strip("0") else None

    moneda = datos.get("moneda")
    return DatosQR(
        ver=_entero(datos.get("ver")),
        fecha=str(datos["fecha"]) if datos.get("fecha") else None,
        cuit=digitos("cuit"),
        pto_vta=_entero(datos.get("ptoVta")),
        tipo_cmp=_entero(datos.get("tipoCmp")),
        nro_cmp=_entero(datos.get("nroCmp")),
        importe=_decimal(datos.get("importe")),
        moneda=str(moneda).strip().upper() if moneda else None,
        ctz=_decimal(datos.get("ctz")),
        tipo_doc_rec=_entero(datos.get("tipoDocRec")),
        nro_doc_rec=digitos("nroDocRec"),
        tipo_cod_aut=str(datos["tipoCodAut"]) if datos.get("tipoCodAut") else None,
        cod_aut=digitos("codAut"),
        reparado=reparado,
        url=url,
    )


def decodificar_url(url: str) -> DatosQR:
    if not es_url_fiscal(url):
        raise QRInvalido("no es una URL de QR fiscal de ARCA/AFIP")
    # parse_qs convierte '+' en espacio; _b64_a_texto lo vuelve a '+'.
    valores = parse_qs(urlparse(url.strip()).query).get("p")
    if not valores:
        raise QRInvalido("la URL no tiene el parámetro p")
    datos, reparado = _parsear_json(_b64_a_texto(valores[0]))
    return normalizar(datos, reparado=reparado, url=url.strip())


def _detectores() -> list:
    # El detector Aruco de OpenCV lee QR densos que el clásico no decodifica;
    # el clásico queda de respaldo para versiones de OpenCV que no lo traen.
    detectores = [cv2.QRCodeDetector()]
    if hasattr(cv2, "QRCodeDetectorAruco"):
        detectores.insert(0, cv2.QRCodeDetectorAruco())
    return detectores


def _decodificar_imagen(imagen: np.ndarray) -> list[str]:
    for detector in _detectores():
        texto = detector.detectAndDecode(imagen)[0]
        if texto:
            return [texto]
    return []


def _imagenes_de_pdf(ruta: Path, max_paginas: int = 2):
    """Primero las imágenes embebidas (el QR suele venir como imagen y a su
    resolución original se lee mejor), después cada página renderizada."""
    with fitz.open(ruta) as pdf:
        for pagina in list(pdf)[:max_paginas]:
            for info in pagina.get_images(full=True):
                imagen = pdf.extract_image(info[0])
                decodificada = cv2.imdecode(np.frombuffer(imagen["image"], np.uint8), cv2.IMREAD_GRAYSCALE)
                if decodificada is not None:
                    yield decodificada
            for zoom in (2.0, 3.0, 4.0):
                pix = pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY)
                yield np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def leer_qr_pdf(ruta: str | Path) -> DatosQR | None:
    """Devuelve el primer QR fiscal legible del PDF, o None si no hay."""
    for imagen in _imagenes_de_pdf(Path(ruta)):
        for texto in _decodificar_imagen(imagen):
            if es_url_fiscal(texto):
                try:
                    return decodificar_url(texto)
                except QRInvalido:
                    continue
    return None
