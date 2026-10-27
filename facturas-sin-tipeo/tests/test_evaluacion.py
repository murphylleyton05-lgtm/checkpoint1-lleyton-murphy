import math

import pytest

from facturas.evaluacion import (
    Tasa, comparar_con_etiqueta, evaluar_contra_qr, evaluar_politica, resumir_operativo, wilson,
)
from facturas.extraccion import ResultadoExtraccion

from conftest import HOY


def resultado(doc_id, factura=None, **extra):
    return ResultadoExtraccion(doc_id=doc_id, config="test", factura=factura, **extra)


def test_wilson_valores_conocidos():
    bajo, alto = wilson(50, 100)
    assert bajo == pytest.approx(0.4038, abs=1e-3) and alto == pytest.approx(0.5962, abs=1e-3)
    bajo, alto = wilson(97, 100)
    assert bajo == pytest.approx(0.9154, abs=1e-3) and alto == pytest.approx(0.9897, abs=1e-3)
    assert all(math.isnan(x) for x in wilson(0, 0))


def test_tasa_texto():
    t = Tasa()
    for ok in (True, True, False, True):
        t.sumar(ok)
    assert t.texto().startswith("75.0% (3/4;")


def test_extraccion_correcta_da_100(lote, qr_de):
    pares = [(resultado(f"d{i}", s.verdad), qr_de(s)) for i, s in enumerate(lote[:-1])]
    reporte = evaluar_contra_qr(pares)
    assert reporte.documento_completo.aciertos == reporte.documento_completo.n == 5
    assert not reporte.discrepancias


def test_falla_de_extraccion_cuenta_como_error_en_todos_los_campos(lote, qr_de):
    s = lote[0]
    reporte = evaluar_contra_qr([(resultado("d0", None, error="x"), qr_de(s))])
    assert reporte.fallas_de_extraccion == 1
    assert all(t.aciertos == 0 for t in reporte.por_campo.values() if t.n)
    assert reporte.documento_completo.aciertos == 0


def test_discrepancias_anonimizan_el_receptor(factura_a, qr_de, monkeypatch):
    monkeypatch.setenv("FACTURAS_SAL", "sal-de-test")
    f = factura_a.verdad
    mala = f.model_copy(update=dict(receptor_nro_doc="30500010912", numero=f.numero + 1))
    reporte = evaluar_contra_qr([(resultado("d0", mala), qr_de(factura_a))])
    por_campo = {d.campo: d for d in reporte.discrepancias}
    assert set(por_campo) == {"numero", "receptor_nro_doc"}
    assert str(por_campo["receptor_nro_doc"].extraido).startswith("anon-")
    assert str(por_campo["receptor_nro_doc"].referencia).startswith("anon-")
    assert f.receptor_nro_doc not in str(por_campo["receptor_nro_doc"].referencia)


def test_comparar_con_etiqueta(factura_a):
    f = factura_a.verdad
    etiqueta = {"importe_neto_gravado": f.importe_neto_gravado,
                "iva": [{"alicuota": 21, "importe": f.iva[0].importe}],
                "items": [i.model_dump() for i in f.items]}
    assert all(comparar_con_etiqueta(f, etiqueta).values())
    mal = f.model_copy(update=dict(importe_neto_gravado=f.importe_neto_gravado + 5))
    assert comparar_con_etiqueta(mal, etiqueta)["importe_neto_gravado"] is False
    assert comparar_con_etiqueta(None, etiqueta) == {
        "importe_neto_gravado": False, "iva": False, "items_cantidad": False, "items_suma": False}


def test_politica(lote, qr_de):
    buenas = [resultado(f"d{i}", s.verdad) for i, s in enumerate(lote[:-1])]
    # Un error que solo el QR atrapa y otro que las reglas atrapan solas.
    s0, s1 = lote[0], lote[1]
    corrido = resultado("x0", s0.verdad.model_copy(update=dict(numero=s0.verdad.numero + 1)))
    cuit_mal = resultado("x1", s1.verdad.model_copy(update=dict(emisor_cuit="30710145765")))
    referencias = {f"d{i}": qr_de(s) for i, s in enumerate(lote[:-1])} | {"x0": qr_de(s0), "x1": qr_de(s1)}
    etiquetas = {"d0": {"importe_total": s0.verdad.importe_total}}
    rep = evaluar_politica(buenas + [corrido, cuit_mal, resultado("falla")], referencias, etiquetas, HOY)
    assert (rep.aprobados_sin_revision.aciertos, rep.aprobados_sin_revision.n) == (5, 8)
    assert (rep.errores_qr_detectados_sin_qr.aciertos, rep.errores_qr_detectados_sin_qr.n) == (1, 2)
    assert (rep.aprobados_correctos_segun_etiqueta.aciertos, rep.aprobados_correctos_segun_etiqueta.n) == (1, 1)
    assert rep.disparos_por_regla["coincide_con_qr"] == 2


def test_resumen_operativo():
    rs = [resultado("a", None, error="API 529: overloaded", costo_usd=None)]
    rs += [resultado(f"b{i}", None, costo_usd=0.01, latencia_s=float(i)) for i in range(1, 4)]
    op = resumir_operativo(rs)
    assert op.documentos == 4 and op.con_error == 1
    assert op.costo_total_usd == pytest.approx(0.03)
    assert op.latencia_p50_s is None  # ninguna con factura: sin latencias de éxito
