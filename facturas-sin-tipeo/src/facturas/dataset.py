"""Manifiesto del dataset: identificadores, referencia del QR y split dev/test.

Decisiones que este módulo fija:
- doc_id = primeros 12 caracteres del SHA-256 del archivo. Renombrar un PDF no
  cambia su identidad y un duplicado exacto se detecta solo.
- El split es por EMISOR, no por documento. Si las facturas de un mismo
  proveedor quedaran repartidas entre dev y test, el prompt podría "aprenderse"
  ese diseño en dev y el test mediría memoria, no generalización.
- El split queda congelado: una vez asignado, no se recalcula aunque cambien
  los parámetros. Documentos nuevos reciben split al entrar.
"""

from __future__ import annotations

import csv
import hashlib
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .modelos import DatosQR
from .qr import leer_qr_pdf

PORCENTAJE_TEST = 30


@dataclass
class EntradaManifiesto:
    doc_id: str
    archivo: str
    origen: str
    emisor_cuit: str
    tiene_qr: bool
    qr_reparado: bool
    split: str


def doc_id(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:12]


def asignar_split(clave_grupo: str, porcentaje_test: int = PORCENTAJE_TEST) -> str:
    cubeta = int(hashlib.sha256(f"split:{clave_grupo}".encode()).hexdigest(), 16) % 100
    return "test" if cubeta < porcentaje_test else "dev"


def anonimizar(valor: str | None, sal: str | None = None) -> str | None:
    """Reemplaza un número de documento por un identificador estable y no reversible."""
    if not valor:
        return valor
    sal = sal if sal is not None else os.environ.get("FACTURAS_SAL", "")
    return "anon-" + hashlib.sha256(f"{sal}:{valor}".encode()).hexdigest()[:8]


def leer_manifiesto(ruta: Path) -> dict[str, EntradaManifiesto]:
    if not ruta.exists():
        return {}
    with ruta.open(newline="", encoding="utf-8") as archivo:
        filas = list(csv.DictReader(archivo))
    entradas = {}
    for fila in filas:
        fila["tiene_qr"] = fila["tiene_qr"] == "True"
        fila["qr_reparado"] = fila["qr_reparado"] == "True"
        entradas[fila["doc_id"]] = EntradaManifiesto(**fila)
    return entradas


def escribir_manifiesto(ruta: Path, entradas: dict[str, EntradaManifiesto]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=[f.name for f in fields(EntradaManifiesto)])
        escritor.writeheader()
        for entrada in sorted(entradas.values(), key=lambda e: e.doc_id):
            escritor.writerow(asdict(entrada))


def ruta_referencia(directorio: Path, doc: str) -> Path:
    return directorio / f"{doc}.json"


def cargar_referencia(directorio: Path, doc: str) -> DatosQR | None:
    ruta = ruta_referencia(directorio, doc)
    if not ruta.exists():
        return None
    return DatosQR.model_validate_json(ruta.read_text(encoding="utf-8"))


def registrar_documentos(entrada: Path, raiz_datos: Path, origen: str) -> tuple[int, int]:
    """Lee el QR de cada PDF nuevo en `entrada`, guarda la referencia y lo suma
    al manifiesto. Devuelve (documentos nuevos, de esos cuántos tienen QR)."""
    manifiesto_ruta = raiz_datos / "manifiesto.csv"
    referencias = raiz_datos / "referencia"
    referencias.mkdir(parents=True, exist_ok=True)
    manifiesto = leer_manifiesto(manifiesto_ruta)

    nuevos = con_qr = 0
    for pdf in sorted(entrada.rglob("*.pdf")):
        doc = doc_id(pdf)
        if doc in manifiesto:
            continue
        qr = leer_qr_pdf(pdf)
        if qr is not None:
            ruta_referencia(referencias, doc).write_text(qr.model_dump_json(indent=2), encoding="utf-8")
            con_qr += 1
        emisor = qr.cuit if qr and qr.cuit else ""
        manifiesto[doc] = EntradaManifiesto(
            doc_id=doc,
            archivo=os.path.relpath(pdf, raiz_datos),
            origen=origen,
            emisor_cuit=emisor,
            tiene_qr=qr is not None,
            qr_reparado=bool(qr and qr.reparado),
            # Sin QR no se conoce el emisor: el documento forma su propio grupo.
            split=asignar_split(emisor or doc),
        )
        nuevos += 1
    escribir_manifiesto(manifiesto_ruta, manifiesto)
    return nuevos, con_qr
