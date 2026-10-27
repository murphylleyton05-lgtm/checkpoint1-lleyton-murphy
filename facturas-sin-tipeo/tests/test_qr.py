import base64
import json

import pytest

from facturas.qr import QRInvalido, decodificar_url, es_url_fiscal, leer_qr_pdf

BASE = "https://www.afip.gob.ar/fe/qr/?p="


def url(carga: str, b64=base64.b64encode) -> str:
    return BASE + b64(carga.encode()).decode()


def test_payload_completo_con_numeros_como_texto():
    # Así llegan algunos QR reales: números entre comillas.
    carga = json.dumps({"ver": "1", "fecha": "2023-11-18", "cuit": 30715327712, "ptoVta": 7, "tipoCmp": 1,
                        "nroCmp": 34748, "importe": "13649.43", "moneda": "PES", "ctz": "1.00",
                        "tipoDocRec": 80, "nroDocRec": 30717336905, "tipoCodAut": "E",
                        "codAut": "73462509910160"})
    qr = decodificar_url(url(carga))
    assert (qr.ver, qr.cuit, qr.pto_vta, qr.nro_cmp) == (1, "30715327712", 7, 34748)
    assert qr.importe == 13649.43 and qr.ctz == 1.0
    assert qr.cod_aut == "73462509910160" and not qr.reparado


def test_qr_sin_fecha():
    qr = decodificar_url(url('{"ver":1,"cuit":33715334319,"ptoVta":20,"tipoCmp":1,"nroCmp":2083,"importe":13964.48}'))
    assert qr.fecha is None and qr.importe == 13964.48


def test_consumidor_final_sin_documento():
    qr = decodificar_url(url('{"ver":1,"cuit":30710145764,"tipoCmp":6,"tipoDocRec":99,"nroDocRec":0}'))
    assert qr.tipo_doc_rec == 99 and qr.nro_doc_rec is None


def test_json_cortado_descarta_el_ultimo_campo():
    # "tipoDocRec": 8 es casi seguro un 80 truncado: no debe usarse como referencia.
    qr = decodificar_url(url('{"ver":1,"cuit":30708910003,"ptoVta":107,"tipoCmp":1,"nroCmp":305,"tipoDocRec":8'))
    assert qr.reparado
    assert qr.nro_cmp == 305 and qr.tipo_doc_rec is None


def test_base64_urlsafe_sin_relleno():
    carga = '{"ver":1,"cuit":30710145764,"ptoVta":4,"tipoCmp":1,"nroCmp":25399,"importe":2460}'
    codificado = base64.urlsafe_b64encode(carga.encode()).decode().rstrip("=")
    assert decodificar_url(BASE + codificado).nro_cmp == 25399


def test_signo_mas_en_la_url_sobrevive():
    # parse_qs convierte '+' en espacio; el decodificador lo tiene que revertir.
    carga = '{"moneda":"~~~"}'  # "~~~" codifica como "fn5+"
    codificado = base64.b64encode(carga.encode()).decode()
    assert "+" in codificado
    assert decodificar_url(BASE + codificado).moneda == "~~~"


@pytest.mark.parametrize("texto, esperado", [
    ("https://www.afip.gob.ar/fe/qr/?p=abc", True),
    ("https://www.arca.gob.ar/fe/qr/?p=abc", True),
    ("https://afip.gob.ar/fe/qr?p=abc", True),
    ("https://www.afip.gob.ar.evil.com/fe/qr/?p=abc", False),
    ("https://www.afip.gob.ar/otra/?p=abc", False),
    ("no es una url", False),
])
def test_solo_urls_fiscales(texto, esperado):
    assert es_url_fiscal(texto) is esperado


def test_rechaza_url_no_fiscal():
    with pytest.raises(QRInvalido):
        decodificar_url("https://example.com/?p=e30=")


def test_lee_el_qr_de_un_pdf(lote, qr_de):
    for sintetica in lote[:-1]:
        leido = leer_qr_pdf(sintetica.ruta)
        assert leido == qr_de(sintetica)
        assert leido.cuit == sintetica.verdad.emisor_cuit


def test_pdf_sin_qr_devuelve_none(lote):
    assert leer_qr_pdf(lote[-1].ruta) is None
