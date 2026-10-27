"""Tablas y validaciones de ARCA (ex AFIP) que usa el resto del proyecto.

Los códigos salen de las tablas de parámetros de factura electrónica de ARCA
(FEParamGetTiposCbte, FEParamGetTiposDoc, FEParamGetTiposIva). Solo están los
comprobantes que aparecen en compras habituales; si llega uno que no está acá,
la regla `tipo_comprobante_conocido` lo marca para revisión en vez de adivinar.
"""

from __future__ import annotations

import re

# código -> (descripción, letra)
TIPOS_COMPROBANTE: dict[int, tuple[str, str]] = {
    1: ("Factura A", "A"),
    2: ("Nota de Débito A", "A"),
    3: ("Nota de Crédito A", "A"),
    4: ("Recibo A", "A"),
    6: ("Factura B", "B"),
    7: ("Nota de Débito B", "B"),
    8: ("Nota de Crédito B", "B"),
    9: ("Recibo B", "B"),
    11: ("Factura C", "C"),
    12: ("Nota de Débito C", "C"),
    13: ("Nota de Crédito C", "C"),
    15: ("Recibo C", "C"),
    51: ("Factura M", "M"),
    52: ("Nota de Débito M", "M"),
    53: ("Nota de Crédito M", "M"),
    201: ("Factura de Crédito Electrónica MiPyME A", "A"),
    202: ("Nota de Débito Electrónica MiPyME A", "A"),
    203: ("Nota de Crédito Electrónica MiPyME A", "A"),
    206: ("Factura de Crédito Electrónica MiPyME B", "B"),
    207: ("Nota de Débito Electrónica MiPyME B", "B"),
    208: ("Nota de Crédito Electrónica MiPyME B", "B"),
    211: ("Factura de Crédito Electrónica MiPyME C", "C"),
    212: ("Nota de Débito Electrónica MiPyME C", "C"),
    213: ("Nota de Crédito Electrónica MiPyME C", "C"),
}

TIPOS_DOCUMENTO: dict[int, str] = {
    80: "CUIT",
    86: "CUIL",
    87: "CDI",
    94: "Pasaporte",
    96: "DNI",
    99: "Consumidor Final / Otro",
}

ALICUOTAS_IVA: frozenset[float] = frozenset({0.0, 2.5, 5.0, 10.5, 21.0, 27.0})

_PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def solo_digitos(valor: object) -> str:
    """Deja solo los dígitos: '30-71014576-4' -> '30710145764'."""
    return re.sub(r"\D", "", str(valor)) if valor is not None else ""


def digito_verificador_cuit(primeros_diez: str) -> int | None:
    """Dígito verificador por módulo 11. Devuelve None si el resultado es 10:
    ARCA nunca emite esos CUIT (cambia el prefijo a 23/33)."""
    suma = sum(int(d) * p for d, p in zip(primeros_diez, _PESOS_CUIT))
    resto = 11 - suma % 11
    if resto == 11:
        return 0
    if resto == 10:
        return None
    return resto


def cuit_valido(valor: object) -> bool:
    digitos = solo_digitos(valor)
    if len(digitos) != 11 or digitos[:2] not in {"20", "23", "24", "27", "30", "33", "34"}:
        return False
    return digito_verificador_cuit(digitos[:10]) == int(digitos[10])


def letra_comprobante(codigo: int) -> str | None:
    tipo = TIPOS_COMPROBANTE.get(codigo)
    return tipo[1] if tipo else None


def describir_comprobante(codigo: int) -> str:
    tipo = TIPOS_COMPROBANTE.get(codigo)
    return tipo[0] if tipo else f"Tipo desconocido ({codigo})"
