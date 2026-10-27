from datetime import timedelta

import pytest

from facturas.modelos import AlicuotaIVA
from facturas.reglas import Contexto, buscar_duplicados, requiere_revision, validar

from conftest import HOY


def nombres(hallazgos, severidad="error"):
    return {h.regla for h in hallazgos if h.severidad == severidad}


def test_facturas_sinteticas_correctas_no_tienen_errores(lote, qr_de):
    for s in lote[:-1]:
        hallazgos = validar(s.verdad, Contexto(hoy=HOY, qr=qr_de(s)))
        assert not requiere_revision(hallazgos), hallazgos


def test_sin_qr_es_advertencia_no_bloqueo(lote):
    hallazgos = validar(lote[0].verdad, Contexto(hoy=HOY, qr=None))
    assert "coincide_con_qr" in nombres(hallazgos, "advertencia")
    assert not requiere_revision(hallazgos)


@pytest.mark.parametrize("cambios, regla", [
    (dict(emisor_cuit="30710145765"), "cuit_emisor_valido"),
    (dict(tipo_comprobante=99), "tipo_comprobante_conocido"),
    (dict(cae="123"), "cae_valido"),
    (dict(cae=None), "cae_valido"),
    (dict(fecha_emision="2030-01-01"), "fecha_valida"),
    (dict(fecha_emision="16/01/2024"), "fecha_valida"),
    (dict(receptor_nro_doc="30717336904"), "documento_receptor_valido"),
])
def test_cada_regla_dispara(factura_a, cambios, regla):
    mala = factura_a.verdad.model_copy(update=cambios)
    assert regla in nombres(validar(mala, Contexto(hoy=HOY)))


def test_total_que_no_cierra(factura_a):
    f = factura_a.verdad
    mala = f.model_copy(update=dict(importe_total=f.importe_total + 100))
    assert "totales_cierran" in nombres(validar(mala, Contexto(hoy=HOY)))


def test_iva_incoherente_con_el_neto(factura_a):
    f = factura_a.verdad
    mala = f.model_copy(update=dict(iva=[AlicuotaIVA(alicuota=21.0, importe=f.iva[0].importe * 1.1)]))
    assert "iva_coherente_con_base" in nombres(validar(mala, Contexto(hoy=HOY)))


def test_alicuota_inexistente(factura_a):
    f = factura_a.verdad
    mala = f.model_copy(update=dict(iva=[AlicuotaIVA(alicuota=12.0, importe=f.iva[0].importe)]))
    assert "alicuotas_validas" in nombres(validar(mala, Contexto(hoy=HOY)))


def test_b_sin_neto_impreso_no_bloquea(lote):
    b = next(s.verdad for s in lote if s.verdad.tipo_comprobante == 6)
    hallazgos = validar(b, Contexto(hoy=HOY))
    assert "totales_cierran" in nombres(hallazgos, "advertencia")
    assert "totales_cierran" not in nombres(hallazgos)


def test_c_con_iva_avisa(lote):
    c = next(s.verdad for s in lote if s.verdad.tipo_comprobante == 11)
    con_iva = c.model_copy(update=dict(iva=[AlicuotaIVA(alicuota=21.0, importe=10.0)]))
    assert "comprobante_c_sin_iva" in nombres(validar(con_iva, Contexto(hoy=HOY)), "advertencia")


def test_comprobante_viejo_avisa(factura_a):
    vieja = factura_a.verdad.model_copy(update=dict(
        fecha_emision=(HOY - timedelta(days=400)).isoformat(), cae_vencimiento=None))
    assert "fecha_valida" in nombres(validar(vieja, Contexto(hoy=HOY)), "advertencia")


def test_discrepancia_con_qr_bloquea(factura_a, qr_de):
    mala = factura_a.verdad.model_copy(update=dict(numero=factura_a.verdad.numero + 1))
    hallazgos = validar(mala, Contexto(hoy=HOY, qr=qr_de(factura_a)))
    assert any(h.regla == "coincide_con_qr" and "numero" in h.detalle for h in hallazgos if h.severidad == "error")
    # Sin QR, un número corrido pasa: es justamente lo que el QR agrega.
    assert not requiere_revision(validar(mala, Contexto(hoy=HOY)))


def test_duplicados(lote):
    a, b = lote[0].verdad, lote[1].verdad
    assert buscar_duplicados({"x": a, "y": a.model_copy(), "z": b}) == {
        f"{a.emisor_cuit}-{a.tipo_comprobante}-{a.punto_venta}-{a.numero}": ["x", "y"]}
