import base64
import hashlib
from types import SimpleNamespace

from facturas import cli, errores
from facturas.cli import main
from facturas.dataset import leer_manifiesto
from facturas.modelos import FacturaExtraida

from conftest import HOY


class ClienteDesdeEtiquetas:
    """Responde cada PDF con su etiqueta sintética, salvo en `sabotear`, donde corre el número."""

    def __init__(self, etiquetas, sabotear=()):
        self.etiquetas, self.sabotear, self.llamadas = etiquetas, set(sabotear), 0
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **pedido):
        self.llamadas += 1
        pdf = base64.b64decode(pedido["messages"][0]["content"][0]["source"]["data"])
        doc = hashlib.sha256(pdf).hexdigest()[:12]
        f = FacturaExtraida.model_validate_json((self.etiquetas / f"{doc}.json").read_text())
        if doc in self.sabotear:
            f = f.model_copy(update=dict(numero=f.numero + 1))
        return SimpleNamespace(parsed_output=f, stop_reason="end_turn", model=pedido["model"],
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=300), _request_id="req")


def test_inyeccion_distingue_lo_que_solo_ve_el_qr(lote, qr_de):
    base = [(s.verdad, qr_de(s)) for s in lote[:-1]]
    reporte = errores.medir(base, HOY)
    r = reporte.por_mutacion
    assert reporte.base_descartada == 0
    # Un dígito mal en el CUIT lo atrapa el dígito verificador, con o sin QR.
    assert r["cuit_un_digito"].detectadas_sin_qr == r["cuit_un_digito"].aplicadas == 5
    # Un número de comprobante corrido es indetectable sin QR.
    assert r["numero_corrido"].detectadas_sin_qr == 0
    assert r["numero_corrido"].detectadas_con_qr == r["numero_corrido"].aplicadas_con_qr == 5
    assert "| `numero_corrido` | 5 | 0% | 100% |" in errores.reporte_markdown(reporte, "test")


def test_circuito_sintetico_sin_api(tmp_path, capsys):
    datos, resultados = tmp_path / "data", tmp_path / "resultados"
    comunes = ["--datos", str(datos), "--resultados", str(resultados)]
    main(comunes + ["sinteticas", "--n", "6", "--sin-qr", "1"])
    manifiesto = leer_manifiesto(datos / "manifiesto.csv")
    assert len(manifiesto) == 6 and sum(e.tiene_qr for e in manifiesto.values()) == 5

    # Regenerar no deja entradas viejas colgadas.
    main(comunes + ["sinteticas", "--n", "4", "--sin-qr", "0"])
    assert len(leer_manifiesto(datos / "manifiesto.csv")) == 4
    assert len(list((datos / "etiquetas").glob("*.json"))) == 4

    main(comunes + ["inyectar", "--origen", "sintetica"])
    assert (resultados / "inyeccion__sintetica.md").exists()
    assert "Errores inyectados" in capsys.readouterr().out


def test_extraer_y_evaluar_de_punta_a_punta(tmp_path, monkeypatch, capsys):
    datos, resultados = tmp_path / "data", tmp_path / "resultados"
    comunes = ["--datos", str(datos), "--resultados", str(resultados)]
    main(comunes + ["sinteticas", "--n", "8", "--sin-qr", "1"])
    con_qr = sorted(e.doc_id for e in leer_manifiesto(datos / "manifiesto.csv").values() if e.tiene_qr)
    cliente = ClienteDesdeEtiquetas(datos / "etiquetas", sabotear=[con_qr[0]])
    monkeypatch.setattr(cli, "_cliente", lambda: cliente)

    def sin_terminal(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", sin_terminal)
    seleccion = ["--origen", "sintetica", "--split", "todos"]
    main(comunes + ["extraer", *seleccion])  # sin terminal y sin --si: no gasta
    assert cliente.llamadas == 0
    main(comunes + ["extraer", *seleccion, "--si"])
    main(comunes + ["extraer", *seleccion, "--si"])  # lo ya procesado no se repite
    assert cliente.llamadas == 8

    main(comunes + ["evaluar", *seleccion])
    reporte = (resultados / "pdf_claude-opus-5-5_medium_v1__todos__sintetica.md").read_text()
    assert "| **Documento completo** | 85.7% (6/7;" in reporte
    assert "| `coincide_con_qr` | 1 |" in reporte
    discrepancias = (datos / "analisis" / "pdf_claude-opus-5-5_medium_v1__todos__sintetica__discrepancias.csv")
    assert discrepancias.read_text().splitlines()[1].startswith(f"{con_qr[0]},numero,")
    capsys.readouterr()
