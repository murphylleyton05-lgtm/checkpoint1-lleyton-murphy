"""Extracción de datos del comprobante con Claude (salida estructurada).

Dos modos para comparar en la evaluación:
- "pdf": se envía el PDF entero; el modelo ve texto e imagen de cada página.
- "texto": se envía solo el texto que PyMuPDF extrae del PDF. Más barato, pero
  pierde la disposición visual y no sirve para PDFs escaneados.

El modelo nunca recibe el contenido del QR: el QR es la referencia contra la que
se mide la extracción, y dárselo invalidaría la medición.
"""

from __future__ import annotations

import base64
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import anthropic
import pymupdf
from pydantic import BaseModel

from .arca import TIPOS_COMPROBANTE
from .modelos import FacturaExtraida

VERSION_PROMPT = "v1"

_TABLA_TIPOS = "\n".join(f"  {codigo}: {desc}" for codigo, (desc, _) in TIPOS_COMPROBANTE.items())

SISTEMA = f"""Transcribís comprobantes fiscales argentinos (facturas, notas de crédito y débito) a datos estructurados para un área de cuentas a pagar. Un error de transcripción termina en un pago o un crédito fiscal mal registrado, así que la prioridad es la fidelidad al documento.

Reglas:
- Transcribí solo lo que está impreso. No calcules ni completes valores que no figuran: si un dato no está, devolvé null (o una lista vacía).
- Los importes argentinos se escriben con punto de miles y coma decimal ("1.234,56"). Devolvelos como número con punto decimal (1234.56).
- CUIT, CAE y números de documento: solo dígitos.
- tipo_comprobante es el código ARCA impreso junto a la letra (por ejemplo "COD. 01" o "Código 006"). Códigos posibles:
{_TABLA_TIPOS}
- punto_venta y numero salen del número completo: en "00004-00025399", el punto de venta es 4 y el número 25399.
- Las fechas suelen estar como DD/MM/AAAA; devolvelas como AAAA-MM-DD.
- importe_neto_gravado es el neto sin IVA. Si el comprobante solo informa "IVA contenido" y no imprime el neto, devolvé null: no lo calcules restando.
- iva lleva una entrada por cada alícuota informada, discriminada o como "IVA contenido", con su importe. base_imponible va solo si está impresa para esa alícuota.
- otros_tributos es la suma de percepciones, impuestos internos y otros tributos impresos.
- receptor_tipo_doc es el código ARCA del documento del receptor (80 CUIT, 86 CUIL, 96 DNI, 99 consumidor final)."""

# Precios de lista de Anthropic en USD por millón de tokens (entrada, salida),
# tomados en octubre de 2026. Verificá los vigentes antes de reportar costos.
PRECIOS_USD_POR_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}

# Modelos que aceptan la re-ejecución automática en otro modelo si el primero
# rechaza el pedido (fallbacks del lado del servidor).
_MODELOS_CON_FALLBACK = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1"}

Esfuerzo = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class ConfigExtraccion:
    modo: Literal["pdf", "texto"] = "pdf"
    modelo: str = "claude-opus-5-5"
    esfuerzo: Esfuerzo = "medium"

    @property
    def nombre(self) -> str:
        return f"{self.modo}_{self.modelo}_{self.esfuerzo}_{VERSION_PROMPT}"


class ResultadoExtraccion(BaseModel):
    doc_id: str
    config: str
    modelo_servido: Optional[str] = None
    factura: Optional[FacturaExtraida] = None
    error: Optional[str] = None
    stop_reason: Optional[str] = None
    tokens_entrada: int = 0
    tokens_salida: int = 0
    costo_usd: Optional[float] = None
    latencia_s: float = 0.0
    request_id: Optional[str] = None
    hash_prompt: str = ""
    procesado_en: str = ""


def hash_prompt() -> str:
    return hashlib.sha256(SISTEMA.encode()).hexdigest()[:10]


def texto_de_pdf(ruta: Path) -> str:
    with pymupdf.open(ruta) as pdf:
        paginas = [p.get_text("text", sort=True) for p in pdf]
    return "\n".join(f"--- página {i} ---\n{t}" for i, t in enumerate(paginas, start=1))


def _contenido(ruta: Path, modo: str) -> list[dict]:
    if modo == "pdf":
        datos = base64.standard_b64encode(ruta.read_bytes()).decode()
        return [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": datos}},
            {"type": "text", "text": "Extraé los datos de este comprobante."},
        ]
    return [{"type": "text", "text": f"<documento>\n{texto_de_pdf(ruta)}\n</documento>\n\n"
                                     "Extraé los datos de este comprobante."}]


def costo_usd(modelo: str, tokens_entrada: int, tokens_salida: int) -> float | None:
    precio = PRECIOS_USD_POR_MTOK.get(modelo)
    if precio is None:
        return None
    return round((tokens_entrada * precio[0] + tokens_salida * precio[1]) / 1_000_000, 6)


def extraer(ruta: str | Path, doc_id: str, config: ConfigExtraccion,
            cliente: anthropic.Anthropic) -> ResultadoExtraccion:
    """Extrae un documento. Los errores de API o de formato quedan registrados en
    el resultado; solo se propagan los que invalidan todo el lote (credenciales)."""
    ruta = Path(ruta)
    resultado = ResultadoExtraccion(
        doc_id=doc_id, config=config.nombre, hash_prompt=hash_prompt(),
        procesado_en=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    pedido = dict(
        model=config.modelo,
        max_tokens=16000,
        system=SISTEMA,
        messages=[{"role": "user", "content": _contenido(ruta, config.modo)}],
        thinking={"type": "adaptive"},
        output_config={"effort": config.esfuerzo},
        output_format=FacturaExtraida,
    )
    if config.modelo in _MODELOS_CON_FALLBACK:
        pedido |= dict(betas=["server-side-fallback-2026-07-01"], fallbacks="default")

    inicio = time.perf_counter()
    try:
        respuesta = cliente.beta.messages.parse(**pedido)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        raise
    except anthropic.APIStatusError as exc:
        resultado.error = f"API {exc.status_code}: {exc.message}"
        return resultado
    except anthropic.APIConnectionError as exc:
        resultado.error = f"conexión: {exc}"
        return resultado
    finally:
        resultado.latencia_s = round(time.perf_counter() - inicio, 3)

    resultado.request_id = getattr(respuesta, "_request_id", None)
    resultado.modelo_servido = respuesta.model
    resultado.stop_reason = respuesta.stop_reason
    resultado.tokens_entrada = respuesta.usage.input_tokens
    resultado.tokens_salida = respuesta.usage.output_tokens
    resultado.costo_usd = costo_usd(respuesta.model, resultado.tokens_entrada, resultado.tokens_salida)

    if respuesta.stop_reason == "refusal":
        resultado.error = "el modelo rechazó el pedido"
    elif respuesta.stop_reason == "max_tokens":
        resultado.error = "respuesta cortada por max_tokens"
    elif respuesta.parsed_output is None:
        resultado.error = "la respuesta no respetó el esquema"
    else:
        resultado.factura = respuesta.parsed_output
    return resultado


def ruta_resultado(directorio: Path, config: ConfigExtraccion, doc_id: str) -> Path:
    return directorio / config.nombre / f"{doc_id}.json"


def guardar(resultado: ResultadoExtraccion, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(resultado.model_dump_json(indent=2), encoding="utf-8")


def cargar(ruta: Path) -> ResultadoExtraccion:
    return ResultadoExtraccion.model_validate_json(ruta.read_text(encoding="utf-8"))
