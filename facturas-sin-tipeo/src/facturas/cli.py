"""Línea de comandos: `facturas <comando>`. Ver `facturas --help`."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from datetime import date
from pathlib import Path

from . import errores, evaluacion
from .dataset import (
    EntradaManifiesto, anonimizar, cargar_referencia, doc_id, escribir_manifiesto, leer_manifiesto,
    registrar_documentos,
)
from .extraccion import ConfigExtraccion, cargar, extraer, guardar, ruta_resultado
from .modelos import FacturaExtraida
from .qr import leer_qr_pdf
from .reglas import Contexto, buscar_duplicados, requiere_revision, validar


def _config(args: argparse.Namespace) -> ConfigExtraccion:
    return ConfigExtraccion(modo=args.modo, modelo=args.modelo, esfuerzo=args.esfuerzo)


def _seleccionar(manifiesto: dict[str, EntradaManifiesto], split: str, origen: str) -> list[EntradaManifiesto]:
    def pasa(e: EntradaManifiesto) -> bool:
        if split != "todos" and e.split != split:
            return False
        if origen == "real":
            return e.origen != "sintetica"
        return origen == "todos" or e.origen == origen
    return [e for e in manifiesto.values() if pasa(e)]


def _cliente():
    import anthropic

    return anthropic.Anthropic(max_retries=4)


def cmd_sinteticas(args: argparse.Namespace) -> None:
    from .sintetica import generar_lote

    datos = Path(args.datos)
    destino = datos / "sinteticas"
    # Regenerar reemplaza el lote anterior entero: sus PDFs cambian y con ellos los doc_id.
    manifiesto = leer_manifiesto(datos / "manifiesto.csv")
    for e in [e for e in manifiesto.values() if e.origen == "sintetica"]:
        for viejo in (datos / "etiquetas" / f"{e.doc_id}.json", datos / "referencia" / f"{e.doc_id}.json"):
            viejo.unlink(missing_ok=True)
        del manifiesto[e.doc_id]
    escribir_manifiesto(datos / "manifiesto.csv", manifiesto)
    for viejo in destino.glob("sintetica_*.pdf"):
        viejo.unlink()

    lote = generar_lote(destino, args.n, semilla=args.semilla, sin_qr=args.sin_qr)
    etiquetas = datos / "etiquetas"
    etiquetas.mkdir(parents=True, exist_ok=True)
    for s in lote:
        # Para las sintéticas la etiqueta es la verdad completa con la que se generó el PDF.
        (etiquetas / f"{doc_id(s.ruta)}.json").write_text(s.verdad.model_dump_json(indent=2), encoding="utf-8")
    nuevos, con_qr = registrar_documentos(destino, datos, origen="sintetica")
    print(f"{len(lote)} facturas sintéticas en {destino} · {nuevos} nuevas en el manifiesto ({con_qr} con QR)")


def cmd_registrar(args: argparse.Namespace) -> None:
    nuevos, con_qr = registrar_documentos(Path(args.entrada), Path(args.datos), origen=args.origen)
    print(f"{nuevos} documentos nuevos · {con_qr} con QR legible · {nuevos - con_qr} sin QR")


def cmd_extraer(args: argparse.Namespace) -> None:
    datos, config = Path(args.datos), _config(args)
    entradas = _seleccionar(leer_manifiesto(datos / "manifiesto.csv"), args.split, args.origen)
    pendientes = [e for e in entradas
                  if args.forzar or not ruta_resultado(datos / "predicciones", config, e.doc_id).exists()]
    if args.limite:
        pendientes = pendientes[: args.limite]
    if not pendientes:
        print("No hay documentos pendientes para esta configuración.")
        return
    print(f"Configuración {config.nombre}: {len(pendientes)} documentos por procesar (split={args.split}, origen={args.origen}).")
    if not args.si:
        try:
            respuesta = input("Cada documento es una llamada paga a la API. ¿Continuar? [s/N] ")
        except EOFError:  # sin terminal (CI, n8n): sin --si no se gasta
            respuesta = ""
        if respuesta.strip().lower() != "s":
            print("Cancelado. Usá --si para correr sin confirmación.")
            return
    cliente, costo = _cliente(), 0.0
    for i, e in enumerate(pendientes, start=1):
        resultado = extraer(datos / e.archivo, e.doc_id, config, cliente)
        guardar(resultado, ruta_resultado(datos / "predicciones", config, e.doc_id))
        costo += resultado.costo_usd or 0
        estado = f"ERROR: {resultado.error}" if resultado.error else "ok"
        print(f"[{i}/{len(pendientes)}] {e.doc_id} {estado} · {resultado.latencia_s:.1f} s · acumulado {costo:.4f} USD")


def _cargar_etiquetas(directorio: Path) -> dict[str, dict]:
    if not directorio.exists():
        return {}
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in directorio.glob("*.json") if p.stem != "EJEMPLO"}


def _baseline_manual(ruta: Path) -> str | None:
    if not ruta.exists():
        return None
    with ruta.open(newline="", encoding="utf-8") as archivo:
        segundos = [float(f["segundos"]) for f in csv.DictReader(archivo) if f.get("segundos")]
    if not segundos:
        return None
    return f"Carga manual cronometrada: {statistics.mean(segundos):.0f} s por documento (n={len(segundos)})"


def cmd_evaluar(args: argparse.Namespace) -> None:
    datos, config = Path(args.datos), _config(args)
    hoy = date.fromisoformat(args.hoy) if args.hoy else date.today()
    entradas = _seleccionar(leer_manifiesto(datos / "manifiesto.csv"), args.split, args.origen)
    resultados, faltantes = [], 0
    for e in entradas:
        ruta = ruta_resultado(datos / "predicciones", config, e.doc_id)
        if ruta.exists():
            resultados.append(cargar(ruta))
        else:
            faltantes += 1
    if not resultados:
        sys.exit("No hay predicciones para evaluar. Corré `facturas extraer` primero.")
    if faltantes:
        print(f"Aviso: {faltantes} documentos del split no tienen predicción y quedan fuera.")

    referencias = {r.doc_id: cargar_referencia(datos / "referencia", r.doc_id) for r in resultados}
    etiquetas = _cargar_etiquetas(datos / "etiquetas")
    rep_qr = evaluacion.evaluar_contra_qr([(r, referencias[r.doc_id]) for r in resultados if referencias[r.doc_id]])
    rep_politica = evaluacion.evaluar_politica(resultados, referencias, etiquetas, hoy)
    rep_operativo = evaluacion.resumir_operativo(resultados)
    n_etiquetas = sum(r.doc_id in etiquetas for r in resultados)

    texto = evaluacion.reporte_markdown(config.nombre, args.split, rep_qr, rep_politica, rep_operativo, n_etiquetas)
    duplicados = buscar_duplicados({r.doc_id: r.factura for r in resultados if r.factura})
    texto += f"\nComprobantes duplicados detectados: {len(duplicados)}\n"
    if baseline := _baseline_manual(datos / "baseline_manual.csv"):
        texto += f"\n{baseline}\n"
    texto += f"\n_Origen de los documentos: {args.origen}. Fecha de referencia de las reglas: {hoy}._\n"

    base = f"{config.nombre}__{args.split}__{args.origen}"
    salida = Path(args.resultados) / f"{base}.md"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(texto, encoding="utf-8")
    # El detalle documento por documento queda local: tiene CUIT de proveedores reales.
    detalle = datos / "analisis" / f"{base}__discrepancias.csv"
    detalle.parent.mkdir(parents=True, exist_ok=True)
    with detalle.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["doc_id", "campo", "extraido", "referencia_qr"])
        for d in rep_qr.discrepancias:
            escritor.writerow([d.doc_id, d.campo, d.extraido, d.referencia])
    print(texto)
    print(f"Reporte: {salida}\nDiscrepancias (local, no se sube): {detalle}")


def cmd_inyectar(args: argparse.Namespace) -> None:
    datos = Path(args.datos)
    hoy = date.fromisoformat(args.hoy) if args.hoy else date.today()
    entradas = _seleccionar(leer_manifiesto(datos / "manifiesto.csv"), "todos", args.origen)
    etiquetas = _cargar_etiquetas(datos / "etiquetas")
    base = []
    for e in entradas:
        etiqueta = etiquetas.get(e.doc_id)
        # Solo sirven etiquetas completas (las sintéticas, o una real etiquetada entera).
        try:
            factura = FacturaExtraida.model_validate(etiqueta) if etiqueta else None
        except ValueError:
            factura = None
        if factura is not None:
            base.append((factura, cargar_referencia(datos / "referencia", e.doc_id)))
    if not base:
        sys.exit("No hay facturas con etiqueta completa para usar de base.")
    texto = errores.reporte_markdown(errores.medir(base, hoy), f"origen {args.origen}, {len(base)} facturas base")
    salida = Path(args.resultados) / f"inyeccion__{args.origen}.md"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"Reporte: {salida}")


def cmd_procesar(args: argparse.Namespace) -> None:
    """Un documento de punta a punta, para mirar a mano (o grabar la demo)."""
    ruta = Path(args.pdf)
    qr = leer_qr_pdf(ruta)
    print(f"QR fiscal: {'leído' if qr else 'no encontrado'}{' (reparado)' if qr and qr.reparado else ''}")
    resultado = extraer(ruta, doc_id(ruta), _config(args), _cliente())
    if resultado.factura is None:
        sys.exit(f"Falló la extracción: {resultado.error}")
    datos = resultado.factura.model_dump()
    datos["receptor_nro_doc"] = anonimizar(datos["receptor_nro_doc"])
    print(json.dumps(datos, indent=2, ensure_ascii=False))
    hallazgos = validar(resultado.factura, Contexto(hoy=date.today(), qr=qr))
    for h in hallazgos:
        print(f"  [{h.severidad}] {h.regla}: {h.detalle}")
    veredicto = "REVISIÓN HUMANA" if requiere_revision(hallazgos) else "APROBADA AUTOMÁTICAMENTE"
    print(f"Veredicto: {veredicto} · {resultado.latencia_s:.1f} s · {resultado.costo_usd} USD")


def _args_config(p: argparse.ArgumentParser) -> None:
    p.add_argument("--modo", choices=["pdf", "texto"], default="pdf")
    p.add_argument("--modelo", default="claude-opus-5-5")
    p.add_argument("--esfuerzo", choices=["low", "medium", "high", "xhigh", "max"], default="medium")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="facturas", description=__doc__)
    parser.add_argument("--datos", default="data", help="carpeta de datos (default: data)")
    parser.add_argument("--resultados", default="resultados", help="carpeta de reportes agregados")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("sinteticas", help="genera facturas sintéticas para probar el circuito")
    p.add_argument("--n", type=int, default=12)
    p.add_argument("--semilla", type=int, default=7)
    p.add_argument("--sin-qr", type=int, default=2)
    p.set_defaults(func=cmd_sinteticas)

    p = sub.add_parser("registrar", help="lee el QR de PDFs nuevos y los suma al manifiesto")
    p.add_argument("--entrada", required=True, help="carpeta con PDFs")
    p.add_argument("--origen", required=True, help="propia, familiar, pyme... (no uses 'sintetica')")
    p.set_defaults(func=cmd_registrar)

    p = sub.add_parser("extraer", help="extrae con Claude los documentos del split")
    _args_config(p)
    p.add_argument("--split", choices=["dev", "test", "todos"], default="dev")
    p.add_argument("--origen", default="real", help="real (todo menos sintéticas), sintetica, todos u otro origen")
    p.add_argument("--limite", type=int, default=0)
    p.add_argument("--forzar", action="store_true", help="vuelve a extraer aunque ya haya resultado")
    p.add_argument("--si", action="store_true", help="no pide confirmación antes de gastar")
    p.set_defaults(func=cmd_extraer)

    p = sub.add_parser("evaluar", help="mide la extracción contra el QR y las etiquetas")
    _args_config(p)
    p.add_argument("--split", choices=["dev", "test", "todos"], default="dev")
    p.add_argument("--origen", default="real")
    p.add_argument("--hoy", help="fecha de referencia AAAA-MM-DD (para reproducir un reporte)")
    p.set_defaults(func=cmd_evaluar)

    p = sub.add_parser("inyectar", help="mide qué errores atrapan las reglas")
    p.add_argument("--origen", default="sintetica")
    p.add_argument("--hoy")
    p.set_defaults(func=cmd_inyectar)

    p = sub.add_parser("procesar", help="procesa un PDF de punta a punta")
    p.add_argument("pdf")
    _args_config(p)
    p.set_defaults(func=cmd_procesar)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
