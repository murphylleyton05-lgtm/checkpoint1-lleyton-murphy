import pytest

from facturas.arca import cuit_valido, digito_verificador_cuit, letra_comprobante, solo_digitos

# CUIT reales de emisores de facturas (públicos), para no depender solo de casos inventados.
CUITS_REALES = ["30710145764", "33715334319", "20340710062", "27309910171", "23317835019", "30708910003"]


@pytest.mark.parametrize("cuit", CUITS_REALES)
def test_cuits_reales_son_validos(cuit):
    assert cuit_valido(cuit)


def test_acepta_guiones_y_espacios():
    assert cuit_valido("30-71014576-4")
    assert cuit_valido(" 30 71014576 4 ")


@pytest.mark.parametrize("cuit", CUITS_REALES)
def test_cambiar_cualquier_digito_lo_invalida(cuit):
    for pos in range(11):
        for nuevo in "0123456789":
            if nuevo == cuit[pos]:
                continue
            alterado = cuit[:pos] + nuevo + cuit[pos + 1:]
            if alterado[:2] in {"20", "23", "24", "27", "30", "33", "34"}:
                assert not cuit_valido(alterado), alterado


@pytest.mark.parametrize("valor", ["", "3071014576", "307101457640", "99710145764", None])
def test_formas_invalidas(valor):
    assert not cuit_valido(valor)


def test_resto_diez_no_tiene_digito():
    # 2*5 + 1*2 = 12; 12 % 11 = 1; 11 - 1 = 10: ARCA no emite ese CUIT.
    assert digito_verificador_cuit("2000000001") is None


def test_letras_y_digitos():
    assert solo_digitos("COD. 01") == "01"
    assert letra_comprobante(1) == "A"
    assert letra_comprobante(211) == "C"
    assert letra_comprobante(999) is None
