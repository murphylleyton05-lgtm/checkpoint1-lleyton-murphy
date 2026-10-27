from datetime import date

import pytest

from facturas.qr import decodificar_url
from facturas.sintetica import generar_lote

HOY = date(2026, 10, 1)


@pytest.fixture(scope="session")
def lote(tmp_path_factory):
    """Seis facturas sintéticas (A, B y C); la última sin QR."""
    return generar_lote(tmp_path_factory.mktemp("sinteticas"), 6, semilla=3, hoy=HOY, sin_qr=1)


@pytest.fixture
def factura_a(lote):
    return next(s for s in lote if s.verdad.tipo_comprobante == 1)


@pytest.fixture
def qr_de():
    return lambda sintetica: decodificar_url(sintetica.url_qr)
