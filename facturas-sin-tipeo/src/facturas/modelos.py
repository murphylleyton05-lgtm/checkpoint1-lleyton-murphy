"""Modelos de datos.

`FacturaExtraida` es a la vez el esquema que se le exige al LLM (salida
estructurada) y lo que validan las reglas. `DatosQR` es la referencia que sale
del QR fiscal y se usa para medir la extracción.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AlicuotaIVA(BaseModel):
    alicuota: float = Field(description="Porcentaje de IVA: 0, 2.5, 5, 10.5, 21 o 27.")
    base_imponible: Optional[float] = Field(
        default=None, description="Neto gravado a esa alícuota, si está impreso."
    )
    importe: float = Field(description="Importe de IVA a esa alícuota.")


class Item(BaseModel):
    descripcion: str
    cantidad: Optional[float] = None
    precio_unitario: Optional[float] = None
    subtotal: Optional[float] = None


class FacturaExtraida(BaseModel):
    emisor_cuit: str = Field(description="CUIT del emisor: 11 dígitos, sin guiones.")
    emisor_razon_social: Optional[str] = None
    tipo_comprobante: int = Field(
        description="Código ARCA del comprobante (1 Factura A, 6 Factura B, 11 Factura C, "
        "3 Nota de Crédito A, etc.). Suele estar impreso como 'COD. 01'."
    )
    punto_venta: int
    numero: int = Field(description="Número de comprobante sin el punto de venta.")
    fecha_emision: str = Field(description="Fecha de emisión en formato AAAA-MM-DD.")
    receptor_tipo_doc: Optional[int] = Field(
        default=None, description="Código ARCA del documento del receptor: 80 CUIT, 86 CUIL, 96 DNI, 99 consumidor final."
    )
    receptor_nro_doc: Optional[str] = Field(default=None, description="Solo dígitos.")
    moneda: str = Field(default="PES", description="Código ARCA de moneda: PES (pesos), DOL (dólares), etc.")
    tipo_cambio: Optional[float] = None
    importe_neto_gravado: Optional[float] = None
    importe_no_gravado: Optional[float] = None
    importe_exento: Optional[float] = None
    iva: list[AlicuotaIVA] = Field(default_factory=list)
    otros_tributos: Optional[float] = Field(
        default=None, description="Suma de percepciones, impuestos internos y otros tributos."
    )
    importe_total: float
    cae: Optional[str] = Field(default=None, description="CAE o CAEA: 14 dígitos.")
    cae_vencimiento: Optional[str] = Field(default=None, description="AAAA-MM-DD.")
    items: list[Item] = Field(default_factory=list)


class DatosQR(BaseModel):
    """Contenido del QR fiscal (RG 4892), ya normalizado.

    Los campos son opcionales porque en la práctica hay QR sin fecha o con el
    JSON cortado. `reparado` indica que hubo que recortar el JSON para leerlo.
    """

    ver: Optional[int] = None
    fecha: Optional[str] = None
    cuit: Optional[str] = None
    pto_vta: Optional[int] = None
    tipo_cmp: Optional[int] = None
    nro_cmp: Optional[int] = None
    importe: Optional[float] = None
    moneda: Optional[str] = None
    ctz: Optional[float] = None
    tipo_doc_rec: Optional[int] = None
    nro_doc_rec: Optional[str] = None
    tipo_cod_aut: Optional[str] = None
    cod_aut: Optional[str] = None
    reparado: bool = False
    url: str = ""
