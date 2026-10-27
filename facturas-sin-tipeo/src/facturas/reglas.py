"""Validaciones deterministas sobre una factura extraída.

La decisión de mandar un documento a revisión humana sale de estas reglas, no
de la "confianza" que el LLM declara sobre sí mismo: una regla falla por un
motivo que se puede explicar y testear.

Severidad:
- error: el documento no se registra sin que una persona lo mire.
- advertencia: se registra, pero queda señalado en el reporte.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Iterable, Literal

from .arca import ALICUOTAS_IVA, TIPOS_COMPROBANTE, cuit_valido, letra_comprobante, solo_digitos
from .modelos import DatosQR, FacturaExtraida

Severidad = Literal["error", "advertencia"]

TOLERANCIA_PESOS = 0.02
ANTIGUEDAD_MAXIMA_DIAS = 365


@dataclass(frozen=True)
class Hallazgo:
    regla: str
    severidad: Severidad
    detalle: str


@dataclass(frozen=True)
class Contexto:
    hoy: date
    qr: DatosQR | None = None
    tolerancia: float = TOLERANCIA_PESOS


Regla = Callable[[FacturaExtraida, Contexto], Iterable[Hallazgo]]
REGLAS: dict[str, Regla] = {}


def regla(funcion: Regla) -> Regla:
    REGLAS[funcion.__name__] = funcion
    return funcion


def _fecha(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


@regla
def cuit_emisor_valido(f: FacturaExtraida, ctx: Contexto):
    if not cuit_valido(f.emisor_cuit):
        yield Hallazgo("cuit_emisor_valido", "error", f"CUIT del emisor inválido: {f.emisor_cuit!r}")


@regla
def documento_receptor_valido(f: FacturaExtraida, ctx: Contexto):
    nro = solo_digitos(f.receptor_nro_doc)
    if f.receptor_tipo_doc in (80, 86) and not cuit_valido(nro):
        yield Hallazgo("documento_receptor_valido", "error", f"CUIT/CUIL del receptor inválido: {nro!r}")
    elif f.receptor_tipo_doc == 96 and not 7 <= len(nro) <= 8:
        yield Hallazgo("documento_receptor_valido", "advertencia", f"DNI del receptor con largo raro: {nro!r}")


@regla
def tipo_comprobante_conocido(f: FacturaExtraida, ctx: Contexto):
    if f.tipo_comprobante not in TIPOS_COMPROBANTE:
        yield Hallazgo("tipo_comprobante_conocido", "error", f"Código de comprobante desconocido: {f.tipo_comprobante}")


@regla
def alicuotas_validas(f: FacturaExtraida, ctx: Contexto):
    for a in f.iva:
        if a.alicuota not in ALICUOTAS_IVA:
            yield Hallazgo("alicuotas_validas", "error", f"Alícuota de IVA inexistente: {a.alicuota}%")


@regla
def iva_coherente_con_base(f: FacturaExtraida, ctx: Contexto):
    for a in f.iva:
        base = a.base_imponible
        # Con una sola alícuota, el neto gravado es la base aunque no esté impreso por alícuota.
        if base is None and len(f.iva) == 1:
            base = f.importe_neto_gravado
        if base is None or a.alicuota not in ALICUOTAS_IVA:
            continue
        esperado = base * a.alicuota / 100
        if abs(esperado - a.importe) > max(ctx.tolerancia, 0.001 * esperado):
            yield Hallazgo("iva_coherente_con_base", "error",
                           f"IVA {a.alicuota}% de {base:.2f} debería ser {esperado:.2f}, figura {a.importe:.2f}")


@regla
def totales_cierran(f: FacturaExtraida, ctx: Contexto):
    netos = [f.importe_neto_gravado, f.importe_no_gravado, f.importe_exento]
    # Sin ningún neto impreso (típico de un B que solo informa "IVA contenido")
    # no hay con qué reconstruir el total: se avisa, pero no se bloquea.
    if all(n is None for n in netos):
        yield Hallazgo("totales_cierran", "advertencia", "Sin netos impresos: no se pudo verificar el total")
        return
    suma = sum(n or 0 for n in netos) + (f.otros_tributos or 0) + sum(a.importe for a in f.iva)
    if abs(suma - f.importe_total) > ctx.tolerancia * max(1, len(f.iva) + 1):
        yield Hallazgo("totales_cierran", "error",
                       f"Neto + IVA + tributos = {suma:.2f}, pero el total es {f.importe_total:.2f}")


@regla
def comprobante_c_sin_iva(f: FacturaExtraida, ctx: Contexto):
    if letra_comprobante(f.tipo_comprobante) == "C" and any(a.importe > 0 for a in f.iva):
        yield Hallazgo("comprobante_c_sin_iva", "advertencia",
                       "Comprobante C con IVA informado: los emisores de C no discriminan IVA")


@regla
def fecha_valida(f: FacturaExtraida, ctx: Contexto):
    fecha = _fecha(f.fecha_emision)
    if fecha is None:
        yield Hallazgo("fecha_valida", "error", f"Fecha de emisión ilegible: {f.fecha_emision!r}")
    elif fecha > ctx.hoy:
        yield Hallazgo("fecha_valida", "error", f"Fecha de emisión futura: {fecha}")
    elif fecha < ctx.hoy - timedelta(days=ANTIGUEDAD_MAXIMA_DIAS):
        yield Hallazgo("fecha_valida", "advertencia", f"Comprobante de más de un año: {fecha}")


@regla
def cae_valido(f: FacturaExtraida, ctx: Contexto):
    cae = solo_digitos(f.cae)
    if not cae:
        yield Hallazgo("cae_valido", "error", "No se encontró CAE/CAEA")
        return
    if len(cae) != 14:
        yield Hallazgo("cae_valido", "error", f"El CAE debe tener 14 dígitos: {cae!r}")
    emision, vencimiento = _fecha(f.fecha_emision), _fecha(f.cae_vencimiento)
    if emision and vencimiento and vencimiento < emision:
        yield Hallazgo("cae_valido", "error", f"El CAE vence ({vencimiento}) antes de la emisión ({emision})")


# Campo del QR -> (campo de FacturaExtraida, cómo comparar)
CAMPOS_QR = {
    "cuit": "emisor_cuit",
    "pto_vta": "punto_venta",
    "tipo_cmp": "tipo_comprobante",
    "nro_cmp": "numero",
    "fecha": "fecha_emision",
    "importe": "importe_total",
    "moneda": "moneda",
    "tipo_doc_rec": "receptor_tipo_doc",
    "nro_doc_rec": "receptor_nro_doc",
    "cod_aut": "cae",
}


def valores_iguales(campo_qr: str, valor_qr, valor_extraido, tolerancia: float = 0.01) -> bool:
    if valor_extraido is None:
        return False
    if campo_qr in ("cuit", "nro_doc_rec", "cod_aut"):
        # El QR suele guardar estos campos como número JSON, que pierde los ceros a la izquierda.
        return solo_digitos(valor_qr).lstrip("0") == solo_digitos(valor_extraido).lstrip("0")
    if campo_qr == "importe":
        return abs(float(valor_qr) - float(valor_extraido)) <= tolerancia
    if campo_qr == "moneda":
        return str(valor_qr).upper() == str(valor_extraido).strip().upper()
    if campo_qr == "fecha":
        return _fecha(str(valor_qr)) == _fecha(str(valor_extraido))
    return int(valor_qr) == int(valor_extraido)


@regla
def coincide_con_qr(f: FacturaExtraida, ctx: Contexto):
    if ctx.qr is None:
        yield Hallazgo("coincide_con_qr", "advertencia", "Sin QR fiscal legible: el encabezado no se pudo verificar")
        return
    for campo_qr, campo in CAMPOS_QR.items():
        valor_qr = getattr(ctx.qr, campo_qr)
        if valor_qr is None:
            continue
        valor = getattr(f, campo)
        if not valores_iguales(campo_qr, valor_qr, valor):
            yield Hallazgo("coincide_con_qr", "error", f"{campo}: extraído {valor!r}, QR {valor_qr!r}")


def validar(f: FacturaExtraida, ctx: Contexto, reglas: Iterable[str] | None = None) -> list[Hallazgo]:
    nombres = list(reglas) if reglas is not None else list(REGLAS)
    return [h for nombre in nombres for h in REGLAS[nombre](f, ctx)]


def requiere_revision(hallazgos: Iterable[Hallazgo]) -> bool:
    return any(h.severidad == "error" for h in hallazgos)


def clave_comprobante(f: FacturaExtraida) -> tuple[str, int, int, int]:
    return (solo_digitos(f.emisor_cuit), f.tipo_comprobante, f.punto_venta, f.numero)


def buscar_duplicados(facturas: dict[str, FacturaExtraida]) -> dict[str, list[str]]:
    """Agrupa doc_id que representan el mismo comprobante (mismo emisor, tipo,
    punto de venta y número). Devuelve solo los grupos con más de un documento."""
    grupos: dict[tuple, list[str]] = {}
    for doc_id, f in facturas.items():
        grupos.setdefault(clave_comprobante(f), []).append(doc_id)
    return {"-".join(map(str, clave)): ids for clave, ids in grupos.items() if len(ids) > 1}
