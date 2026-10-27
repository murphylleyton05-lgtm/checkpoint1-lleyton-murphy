"""Inyección de errores para medir qué atrapan las reglas.

Se parte de facturas correctas y se introduce un error típico de transcripción
por vez. La tabla resultante dice qué errores atrapan las reglas por sí solas y
cuáles solo se detectan gracias al QR: esa es la justificación de leer el QR.

Es una medición de las reglas, no del sistema: la frecuencia de cada error en
producción sale de la evaluación con documentos reales.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from .modelos import DatosQR, FacturaExtraida
from .reglas import Contexto, requiere_revision, validar

Mutacion = Callable[[FacturaExtraida, random.Random, date], FacturaExtraida | None]
MUTACIONES: dict[str, Mutacion] = {}


def mutacion(funcion: Mutacion) -> Mutacion:
    MUTACIONES[funcion.__name__] = funcion
    return funcion


def _copia(f: FacturaExtraida, **cambios) -> FacturaExtraida:
    return f.model_copy(deep=True, update=cambios)


@mutacion
def cuit_un_digito(f, rng, hoy):
    pos = rng.randrange(11)
    nuevo = str((int(f.emisor_cuit[pos]) + rng.randint(1, 9)) % 10)
    return _copia(f, emisor_cuit=f.emisor_cuit[:pos] + nuevo + f.emisor_cuit[pos + 1:])


@mutacion
def cuit_transposicion(f, rng, hoy):
    candidatos = [i for i in range(2, 10) if f.emisor_cuit[i] != f.emisor_cuit[i + 1]]
    if not candidatos:
        return None
    i = rng.choice(candidatos)
    c = f.emisor_cuit
    return _copia(f, emisor_cuit=c[:i] + c[i + 1] + c[i] + c[i + 2:])


@mutacion
def total_alterado(f, rng, hoy):
    factor = 1 + rng.choice([-1, 1]) * rng.uniform(0.01, 0.1)
    return _copia(f, importe_total=round(f.importe_total * factor, 2))


@mutacion
def iva_alterado(f, rng, hoy):
    if not f.iva:
        return None
    iva = [a.model_copy() for a in f.iva]
    iva[0].importe = round(iva[0].importe * 1.1, 2)
    return _copia(f, iva=iva)


@mutacion
def alicuota_inexistente(f, rng, hoy):
    if not f.iva:
        return None
    iva = [a.model_copy() for a in f.iva]
    iva[0].alicuota = 12.0
    return _copia(f, iva=iva)


@mutacion
def numero_corrido(f, rng, hoy):
    return _copia(f, numero=f.numero + 1)


@mutacion
def punto_venta_corrido(f, rng, hoy):
    return _copia(f, punto_venta=f.punto_venta + 1)


@mutacion
def letra_equivocada(f, rng, hoy):
    cambio = {1: 6, 6: 1, 11: 6, 3: 8, 8: 3}
    if f.tipo_comprobante not in cambio:
        return None
    return _copia(f, tipo_comprobante=cambio[f.tipo_comprobante])


@mutacion
def fecha_futura(f, rng, hoy):
    return _copia(f, fecha_emision=(hoy + timedelta(days=rng.randint(5, 60))).isoformat())


@mutacion
def fecha_dia_mes_invertidos(f, rng, hoy):
    fecha = date.fromisoformat(f.fecha_emision)
    if fecha.day > 12 or fecha.day == fecha.month:
        return None
    return _copia(f, fecha_emision=fecha.replace(month=fecha.day, day=fecha.month).isoformat())


@mutacion
def cae_truncado(f, rng, hoy):
    if not f.cae:
        return None
    return _copia(f, cae=f.cae[:-1])


@dataclass
class ResultadoMutacion:
    aplicadas: int = 0
    detectadas_sin_qr: int = 0
    aplicadas_con_qr: int = 0
    detectadas_con_qr: int = 0


@dataclass
class ReporteInyeccion:
    por_mutacion: dict[str, ResultadoMutacion] = field(default_factory=dict)
    base_descartada: int = 0


def medir(base: list[tuple[FacturaExtraida, DatosQR | None]], hoy: date, semilla: int = 11) -> ReporteInyeccion:
    """`base` son facturas correctas con su QR. Las que ya disparan un error
    antes de mutarlas se descartan: no servirían para atribuir la detección."""
    rng = random.Random(semilla)
    reporte = ReporteInyeccion(por_mutacion={m: ResultadoMutacion() for m in MUTACIONES})
    for f, qr in base:
        if requiere_revision(validar(f, Contexto(hoy=hoy, qr=qr))):
            reporte.base_descartada += 1
            continue
        for nombre, mutar in MUTACIONES.items():
            mutada = mutar(f, rng, hoy)
            if mutada is None:
                continue
            r = reporte.por_mutacion[nombre]
            r.aplicadas += 1
            r.detectadas_sin_qr += requiere_revision(validar(mutada, Contexto(hoy=hoy, qr=None)))
            if qr is not None:
                r.aplicadas_con_qr += 1
                r.detectadas_con_qr += requiere_revision(validar(mutada, Contexto(hoy=hoy, qr=qr)))
    return reporte


def reporte_markdown(reporte: ReporteInyeccion, origen: str) -> str:
    lineas = [
        f"# Errores inyectados: qué detectan las reglas ({origen})",
        "",
        f"Facturas base descartadas por tener ya un error: {reporte.base_descartada}",
        "",
        "«Detectados con QR» se calcula solo sobre las facturas base que tienen QR.",
        "",
        "| Error inyectado | Casos | Detectados sin QR | Detectados con QR |",
        "|---|---|---|---|",
    ]
    for nombre, r in reporte.por_mutacion.items():
        if not r.aplicadas:
            continue
        con_qr = f"{r.detectadas_con_qr / r.aplicadas_con_qr:.0%}" if r.aplicadas_con_qr else "sin QR"
        lineas.append(f"| `{nombre}` | {r.aplicadas} | {r.detectadas_sin_qr / r.aplicadas:.0%} | {con_qr} |")
    return "\n".join(lineas) + "\n"
