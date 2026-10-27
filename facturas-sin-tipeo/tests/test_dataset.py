import shutil

from facturas.dataset import (
    anonimizar, asignar_split, cargar_referencia, doc_id, leer_manifiesto, registrar_documentos,
)


def test_split_es_por_grupo_y_estable():
    assert asignar_split("30710145764") == asignar_split("30710145764")
    splits = [asignar_split(str(i)) for i in range(2000)]
    proporcion_test = splits.count("test") / len(splits)
    assert 0.25 < proporcion_test < 0.35


def test_anonimizar_es_estable_y_depende_de_la_sal():
    assert anonimizar("30717336905", "a") == anonimizar("30717336905", "a")
    assert anonimizar("30717336905", "a") != anonimizar("30717336905", "b")
    assert anonimizar(None, "a") is None


def test_registrar_documentos(lote, tmp_path):
    entrada = tmp_path / "crudas"
    entrada.mkdir()
    for s in lote:
        shutil.copy(s.ruta, entrada / s.ruta.name)
    datos = tmp_path / "data"

    assert registrar_documentos(entrada, datos, origen="propia") == (6, 5)
    manifiesto = leer_manifiesto(datos / "manifiesto.csv")
    assert len(manifiesto) == 6
    con_qr = [e for e in manifiesto.values() if e.tiene_qr]
    assert {e.emisor_cuit for e in con_qr} == {s.verdad.emisor_cuit for s in lote[:-1]}
    # El split sigue al emisor.
    assert all(e.split == asignar_split(e.emisor_cuit) for e in con_qr)
    referencia = cargar_referencia(datos / "referencia", doc_id(lote[0].ruta))
    assert referencia.nro_cmp == lote[0].verdad.numero

    # Correr de nuevo no duplica ni re-asigna nada.
    assert registrar_documentos(entrada, datos, origen="propia") == (0, 0)
    assert leer_manifiesto(datos / "manifiesto.csv") == manifiesto
