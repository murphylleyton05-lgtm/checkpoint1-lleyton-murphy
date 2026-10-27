"""El cliente de Anthropic se reemplaza por un doble: los tests no gastan ni necesitan clave."""

from types import SimpleNamespace

import anthropic
import httpx2 as httpx  # el SDK de Anthropic 2.x usa httpx2
import pytest

from facturas.extraccion import ConfigExtraccion, costo_usd, extraer, texto_de_pdf


class ClienteFalso:
    def __init__(self, respuesta=None, excepcion=None):
        self.pedidos = []
        self._respuesta, self._excepcion = respuesta, excepcion
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **pedido):
        self.pedidos.append(pedido)
        if self._excepcion:
            raise self._excepcion
        return self._respuesta


def respuesta(parsed, stop_reason="end_turn", modelo="claude-opus-5-5"):
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason, model=modelo,
                           usage=SimpleNamespace(input_tokens=2000, output_tokens=500), _request_id="req_test")


def test_extraccion_ok_registra_uso_y_costo(factura_a):
    cliente = ClienteFalso(respuesta(factura_a.verdad))
    r = extraer(factura_a.ruta, "d0", ConfigExtraccion(), cliente)
    assert r.factura == factura_a.verdad and r.error is None
    assert r.costo_usd == pytest.approx((2000 * 4 + 500 * 20) / 1e6)
    assert r.request_id == "req_test" and r.config == "pdf_claude-opus-5-5_medium_v1"


def test_modo_pdf_manda_el_documento_y_pide_fallback(factura_a):
    cliente = ClienteFalso(respuesta(factura_a.verdad))
    extraer(factura_a.ruta, "d0", ConfigExtraccion(modo="pdf"), cliente)
    pedido = cliente.pedidos[0]
    bloque = pedido["messages"][0]["content"][0]
    assert bloque["type"] == "document" and bloque["source"]["media_type"] == "application/pdf"
    assert pedido["fallbacks"] == "default" and pedido["betas"] == ["server-side-fallback-2026-07-01"]
    assert pedido["output_config"] == {"effort": "medium"}


def test_modo_texto_no_manda_el_pdf_ni_el_qr(factura_a):
    cliente = ClienteFalso(respuesta(factura_a.verdad, modelo="claude-haiku-5-5"))
    extraer(factura_a.ruta, "d0", ConfigExtraccion(modo="texto", modelo="claude-haiku-5-5"), cliente)
    pedido = cliente.pedidos[0]
    texto = pedido["messages"][0]["content"][0]["text"]
    assert "Importe Total" in texto and "fe/qr" not in texto
    assert "fallbacks" not in pedido  # Haiku no tiene fallback del lado del servidor


@pytest.mark.parametrize("stop_reason, error", [
    ("refusal", "el modelo rechazó el pedido"),
    ("max_tokens", "respuesta cortada por max_tokens"),
])
def test_cortes_quedan_registrados(factura_a, stop_reason, error):
    r = extraer(factura_a.ruta, "d0", ConfigExtraccion(), ClienteFalso(respuesta(None, stop_reason)))
    assert r.factura is None and r.error == error


def _error_api(clase, status):
    pedido = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return clase("falla", response=httpx.Response(status, request=pedido), body=None)


def test_error_de_api_no_corta_el_lote(factura_a):
    r = extraer(factura_a.ruta, "d0", ConfigExtraccion(),
                ClienteFalso(excepcion=_error_api(anthropic.InternalServerError, 500)))
    assert r.factura is None and r.error.startswith("API 500")


def test_credenciales_invalidas_si_cortan(factura_a):
    with pytest.raises(anthropic.AuthenticationError):
        extraer(factura_a.ruta, "d0", ConfigExtraccion(),
                ClienteFalso(excepcion=_error_api(anthropic.AuthenticationError, 401)))


def test_costo_de_modelo_desconocido_es_none():
    assert costo_usd("modelo-x", 10, 10) is None


def test_texto_de_pdf(factura_a):
    assert factura_a.verdad.cae in texto_de_pdf(factura_a.ruta)
