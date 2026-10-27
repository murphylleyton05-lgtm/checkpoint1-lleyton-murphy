"""Métricas de la extracción y de la política de revisión.

Tres mediciones distintas, a propósito separadas:

1. Exactitud por campo contra el QR. Mide al LLM solo, con una referencia que
   no depende de mí (el QR la genera el sistema del emisor).
2. Exactitud contra etiquetas manuales en los campos que el QR no trae (IVA,
   netos, ítems). Muestra más chica, etiquetada a mano.
3. Política de revisión. Ojo con la circularidad: la regla `coincide_con_qr`
   usa el mismo QR que la medición 1, así que "lo aprobado coincide con el QR"
   es cierto por construcción. El error residual de lo aprobado se mide solo
   con etiquetas manuales, y aparte se reporta cuántos errores del LLM
   detectan las reglas SIN mirar el QR (el caso de un documento sin QR).

Cada tasa va con su intervalo de Wilson al 95 %: con 100 documentos, "97 %"
puede ser cualquier cosa entre ~91 % y ~99 %, y el reporte lo tiene que decir.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date

from .dataset import anonimizar
from .extraccion import ResultadoExtraccion
from .modelos import DatosQR, FacturaExtraida
from .reglas import CAMPOS_QR, Contexto, requiere_revision, validar, valores_iguales

CAMPOS_ANONIMIZADOS = {"nro_doc_rec", "receptor_nro_doc"}
CAMPOS_MANUALES_NUMERICOS = (
    "importe_neto_gravado", "importe_no_gravado", "importe_exento", "otros_tributos", "importe_total",
)


def wilson(aciertos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = aciertos / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centro - margen), min(1.0, centro + margen))


@dataclass
class Tasa:
    aciertos: int = 0
    n: int = 0

    def sumar(self, ok: bool) -> None:
        self.n += 1
        self.aciertos += int(ok)

    @property
    def valor(self) -> float:
        return self.aciertos / self.n if self.n else math.nan

    def texto(self) -> str:
        if not self.n:
            return "sin datos"
        bajo, alto = wilson(self.aciertos, self.n)
        return f"{self.valor:.1%} ({self.aciertos}/{self.n}; IC95 {bajo:.1%}–{alto:.1%})"


@dataclass
class Discrepancia:
    doc_id: str
    campo: str
    extraido: object
    referencia: object


@dataclass
class ReporteQR:
    por_campo: dict[str, Tasa] = field(default_factory=dict)
    documento_completo: Tasa = field(default_factory=Tasa)
    fallas_de_extraccion: int = 0
    discrepancias: list[Discrepancia] = field(default_factory=list)


def _mostrar(campo: str, valor: object) -> object:
    return anonimizar(str(valor)) if campo in CAMPOS_ANONIMIZADOS and valor is not None else valor


def evaluar_contra_qr(pares: list[tuple[ResultadoExtraccion, DatosQR]]) -> ReporteQR:
    """Una extracción fallida cuenta como error en todos sus campos: si se
    descartara, la exactitud se inflaría justo con los documentos difíciles."""
    reporte = ReporteQR(por_campo={c: Tasa() for c in CAMPOS_QR})
    for resultado, qr in pares:
        f = resultado.factura
        if f is None:
            reporte.fallas_de_extraccion += 1
        todo_bien = True
        for campo_qr, campo in CAMPOS_QR.items():
            valor_qr = getattr(qr, campo_qr)
            if valor_qr is None:
                continue
            valor = getattr(f, campo) if f is not None else None
            ok = valores_iguales(campo_qr, valor_qr, valor)
            reporte.por_campo[campo_qr].sumar(ok)
            todo_bien &= ok
            if not ok:
                reporte.discrepancias.append(Discrepancia(
                    resultado.doc_id, campo, _mostrar(campo, valor), _mostrar(campo_qr, valor_qr)))
        reporte.documento_completo.sumar(todo_bien)
    return reporte


def _iva_igual(extraido: list, etiqueta: list[dict], tolerancia: float) -> bool:
    a = sorted((x.alicuota, x.importe) for x in extraido)
    b = sorted((float(x["alicuota"]), float(x["importe"])) for x in etiqueta)
    return len(a) == len(b) and all(p[0] == q[0] and abs(p[1] - q[1]) <= tolerancia for p, q in zip(a, b))


def comparar_con_etiqueta(f: FacturaExtraida | None, etiqueta: dict,
                          tolerancia: float = 0.01) -> dict[str, bool]:
    """Compara solo los campos que la etiqueta manual trae."""
    resultado: dict[str, bool] = {}
    for campo in CAMPOS_MANUALES_NUMERICOS:
        if campo not in etiqueta:
            continue
        esperado, valor = etiqueta[campo], getattr(f, campo) if f else None
        if esperado is None:
            resultado[campo] = valor is None
        else:
            resultado[campo] = valor is not None and abs(float(esperado) - valor) <= tolerancia
    if "iva" in etiqueta:
        resultado["iva"] = f is not None and _iva_igual(f.iva, etiqueta["iva"], tolerancia)
    if "items" in etiqueta:
        esperados = etiqueta["items"]
        resultado["items_cantidad"] = f is not None and len(f.items) == len(esperados)
        suma_esperada = sum(float(i.get("subtotal") or 0) for i in esperados)
        resultado["items_suma"] = f is not None and abs(
            sum(i.subtotal or 0 for i in f.items) - suma_esperada) <= tolerancia * max(1, len(esperados))
    return resultado


@dataclass
class ReportePolitica:
    aprobados_sin_revision: Tasa = field(default_factory=Tasa)
    errores_qr_detectados_sin_qr: Tasa = field(default_factory=Tasa)
    aprobados_correctos_segun_etiqueta: Tasa = field(default_factory=Tasa)
    disparos_por_regla: dict[str, int] = field(default_factory=dict)


def evaluar_politica(resultados: list[ResultadoExtraccion], referencias: dict[str, DatosQR | None],
                     etiquetas: dict[str, dict], hoy: date) -> ReportePolitica:
    reporte = ReportePolitica()
    for resultado in resultados:
        f = resultado.factura
        if f is None:
            reporte.aprobados_sin_revision.sumar(False)  # una falla de extracción siempre va a revisión
            continue
        qr = referencias.get(resultado.doc_id)
        hallazgos = validar(f, Contexto(hoy=hoy, qr=qr))
        for nombre in {h.regla for h in hallazgos if h.severidad == "error"}:
            reporte.disparos_por_regla[nombre] = reporte.disparos_por_regla.get(nombre, 0) + 1
        aprobado = not requiere_revision(hallazgos)
        reporte.aprobados_sin_revision.sumar(aprobado)

        if qr is not None:
            errores_qr = [c for c, campo in CAMPOS_QR.items()
                          if getattr(qr, c) is not None and not valores_iguales(c, getattr(qr, c), getattr(f, campo))]
            if errores_qr:
                sin_qr = validar(f, Contexto(hoy=hoy, qr=None))
                reporte.errores_qr_detectados_sin_qr.sumar(requiere_revision(sin_qr))

        etiqueta = etiquetas.get(resultado.doc_id)
        if aprobado and etiqueta:
            reporte.aprobados_correctos_segun_etiqueta.sumar(all(comparar_con_etiqueta(f, etiqueta).values()))
    return reporte


@dataclass
class ReporteOperativo:
    documentos: int
    con_error: int
    errores: dict[str, int]
    costo_total_usd: float | None
    costo_medio_usd: float | None
    latencia_p50_s: float | None
    latencia_p90_s: float | None
    tokens_entrada_medio: float | None
    tokens_salida_medio: float | None


def resumir_operativo(resultados: list[ResultadoExtraccion]) -> ReporteOperativo:
    errores: dict[str, int] = {}
    for r in resultados:
        if r.error:
            errores[r.error] = errores.get(r.error, 0) + 1
    costos = [r.costo_usd for r in resultados if r.costo_usd is not None]
    latencias = sorted(r.latencia_s for r in resultados if r.factura is not None)

    def percentil(valores: list[float], p: float) -> float | None:
        if not valores:
            return None
        return valores[min(len(valores) - 1, math.ceil(p * len(valores)) - 1)]

    ok = [r for r in resultados if r.factura is not None]
    return ReporteOperativo(
        documentos=len(resultados),
        con_error=sum(errores.values()),
        errores=errores,
        costo_total_usd=round(sum(costos), 4) if costos else None,
        costo_medio_usd=round(statistics.mean(costos), 5) if costos else None,
        latencia_p50_s=percentil(latencias, 0.5),
        latencia_p90_s=percentil(latencias, 0.9),
        tokens_entrada_medio=round(statistics.mean(r.tokens_entrada for r in ok), 1) if ok else None,
        tokens_salida_medio=round(statistics.mean(r.tokens_salida for r in ok), 1) if ok else None,
    )


def reporte_markdown(nombre: str, split: str, qr: ReporteQR, politica: ReportePolitica,
                     operativo: ReporteOperativo, n_etiquetas: int) -> str:
    lineas = [
        f"# Evaluación: `{nombre}` · split `{split}`",
        "",
        f"Documentos: {operativo.documentos} · con QR: {qr.documento_completo.n} · "
        f"fallas de extracción: {operativo.con_error} · con etiqueta manual: {n_etiquetas}",
        "",
        "## 1. Exactitud por campo contra el QR fiscal",
        "",
        "| Campo | Exactitud (aciertos/n; IC 95 %) |",
        "|---|---|",
    ]
    lineas += [f"| `{c}` | {t.texto()} |" for c, t in qr.por_campo.items() if t.n]
    lineas += [
        f"| **Documento completo** | {qr.documento_completo.texto()} |",
        "",
        "## 2. Política de revisión",
        "",
        f"- Aprobados sin revisión humana: {politica.aprobados_sin_revision.texto()}",
        f"- Errores del LLM en campos del QR que las reglas detectan sin mirar el QR: "
        f"{politica.errores_qr_detectados_sin_qr.texto()}",
        f"- Aprobados correctos según etiqueta manual (IVA, netos, ítems): "
        f"{politica.aprobados_correctos_segun_etiqueta.texto()}",
        "",
        "| Regla | Documentos bloqueados |",
        "|---|---|",
    ]
    lineas += [f"| `{r}` | {n} |" for r, n in sorted(politica.disparos_por_regla.items(), key=lambda x: -x[1])]
    lineas += [
        "",
        "## 3. Costo y latencia",
        "",
        f"- Costo total: {operativo.costo_total_usd} USD · por documento: {operativo.costo_medio_usd} USD",
        f"- Latencia p50: {operativo.latencia_p50_s} s · p90: {operativo.latencia_p90_s} s",
        f"- Tokens medios: entrada {operativo.tokens_entrada_medio} · salida {operativo.tokens_salida_medio}",
    ]
    if operativo.errores:
        lineas += ["", "Fallas de extracción:", ""]
        lineas += [f"- {e}: {n}" for e, n in operativo.errores.items()]
    return "\n".join(lineas) + "\n"
