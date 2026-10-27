# Facturas sin tipeo

Extracción de datos de facturas argentinas con IA, **verificada contra el QR fiscal de ARCA**, con revisión humana solo donde las reglas encuentran un problema.

> **Estado: v0.1 (semana 1).** El circuito completo funciona y está testeado con facturas sintéticas. **Todavía no hay resultados con facturas reales**: la sección de resultados se completa cuando termine la recolección (ver [`data/README.md`](data/README.md)). Acá no hay números inventados.

## El problema

En un estudio contable o en un área de cuentas a pagar, cada factura de proveedor se tipea a mano en el sistema: CUIT, número, fecha, netos, IVA, percepciones, total. Es trabajo lento y de bajo valor, y los errores (un dígito del CUIT, un total mal copiado, una factura cargada dos veces) terminan en pagos o créditos fiscales mal registrados.

Un LLM puede leer la factura, pero «casi siempre bien» no alcanza para registrar un comprobante. La pregunta de este proyecto no es *si* la IA puede extraer facturas, sino **cuánto acierta, cuánto cuesta y cómo se detecta cuando se equivoca**.

## Qué hace

```
PDF ──► QR fiscal (RG 4892) ──────────────────────────┐ referencia independiente
  │                                                   ▼
  └──► Claude (salida estructurada) ──► FacturaExtraida ──► 10 reglas deterministas
                                                                 │
                                         sin errores ◄───────────┴──────► con errores
                                         registro automático               revisión humana
```

1. **Lee el QR fiscal** del PDF (OpenCV) y lo decodifica tolerando lo que aparece en facturas reales: números como texto, campos faltantes, JSON cortado.
2. **Extrae** encabezado, netos, IVA por alícuota, percepciones e ítems con Claude, usando un esquema Pydantic como salida estructurada. Hay dos modos para comparar: el PDF completo o solo el texto extraído.
3. **Valida** con reglas que no dependen del LLM: dígito verificador del CUIT, neto + IVA + tributos = total, IVA coherente con el neto, alícuotas existentes, CAE de 14 dígitos, fechas posibles, coincidencia con el QR y duplicados.
4. **Decide**: si alguna regla da `error`, el documento va a revisión; si no, se registra.

## Cómo se evalúa

Tres mediciones separadas. Los motivos están en [`docs/decisiones.md`](docs/decisiones.md), D5.

| Medición | Referencia | Qué responde |
|---|---|---|
| Exactitud por campo | QR fiscal (lo genera el sistema del emisor) | ¿Cuánto acierta el LLM solo? |
| Error residual en lo aprobado | Etiquetas manuales (IVA, netos, ítems) | De lo que se registra sin revisión, ¿cuánto está mal? |
| Detección sin QR | Errores del LLM vs. reglas sin mirar el QR | ¿Qué pasa con un comprobante que no trae QR? |

Además, cada reporte incluye costo y latencia por documento y la comparación con la carga manual cronometrada. Toda tasa va con su intervalo de confianza de Wilson al 95 %. El split dev/test es por emisor y está congelado.

## Resultados

### Con facturas reales

_Pendiente._ Se completa con la salida de `facturas evaluar ... --split test` cuando haya ≥ 100 comprobantes reales de ≥ 15 emisores.

### Qué atrapan las reglas (errores inyectados en facturas sintéticas)

Esto mide las reglas, no el sistema: en 40 facturas sintéticas correctas se inyectó un error típico por vez (`make demo`, reporte en [`resultados/inyeccion__sintetica.md`](resultados/inyeccion__sintetica.md)). La columna «con QR» se calcula sobre las 36 que tienen QR.

| Error inyectado | Detectado sin QR | Detectado con QR |
|---|---|---|
| Un dígito del CUIT cambiado | 100 % | 100 % |
| Dos dígitos del CUIT transpuestos | 100 % | 100 % |
| Total alterado 1–10 % | 50 % | 100 % |
| IVA alterado 10 % | 67 % | 67 % |
| Alícuota inexistente | 100 % | 100 % |
| Número de comprobante corrido | 0 % | 100 % |
| Punto de venta corrido | 0 % | 100 % |
| Letra equivocada (A↔B) | 0 % | 100 % |
| Fecha futura | 100 % | 100 % |
| Día y mes invertidos | 27 % | 100 % |
| CAE truncado | 100 % | 100 % |

Lo que muestra:
- El QR es la única defensa contra un número, un punto de venta o una letra mal leídos.
- El IVA de las facturas B no se puede verificar ni siquiera con QR: el QR no trae IVA y el B no imprime el neto. Por eso existen las etiquetas manuales.

## Cómo correrlo

```bash
make instalar                 # crea .venv e instala el paquete con dependencias de desarrollo
make test                     # tests: no usan la API
make demo                     # 40 facturas sintéticas + reporte de errores inyectados
```

Con facturas reales (necesita `ANTHROPIC_API_KEY`; cada documento es una llamada paga):

```bash
cp .env.example .env          # completar la clave y la sal de anonimización
set -a && . ./.env && set +a

.venv/bin/facturas registrar --entrada data/crudas/propias --origen propia
.venv/bin/facturas extraer --split dev                      # pide confirmación antes de gastar
.venv/bin/facturas evaluar --split dev
.venv/bin/facturas extraer --split dev --modo texto         # segunda configuración para comparar
.venv/bin/facturas procesar data/crudas/propias/factura.pdf # un documento de punta a punta
```

El modelo por defecto es `claude-opus-5-5` con esfuerzo `medium`; se cambian con `--modelo` y `--esfuerzo`. Cada configuración guarda sus predicciones aparte (`data/predicciones/<config>/`) y no repite documentos ya procesados.

## Datos y privacidad

- Ningún documento ni dato derivado por documento se sube al repositorio (`data/` está en `.gitignore`).
- Los reportes que se publican son agregados. El documento del receptor se anonimiza con un hash con sal.
- Los documentos de terceros se usan con consentimiento. El protocolo completo está en [`data/README.md`](data/README.md).

## Limitaciones conocidas

- Lectura de QR probada solo con PDFs sintéticos (60/60). Los PDFs escaneados o con QR de baja resolución están sin medir.
- Las reglas no conocen la condición frente al IVA del receptor, así que una letra equivocada solo se detecta con QR.
- Los precios para calcular costos están en `src/facturas/extraccion.py` (octubre 2026): verificarlos antes de reportar.

## Estructura

```
src/facturas/
  arca.py         tablas de ARCA y dígito verificador del CUIT
  qr.py           lectura y decodificación del QR fiscal
  modelos.py      esquemas Pydantic (salida del LLM y referencia del QR)
  extraccion.py   extracción con Claude, costo y latencia
  reglas.py       validaciones deterministas y duplicados
  evaluacion.py   métricas con intervalos de Wilson
  errores.py      inyección de errores para medir las reglas
  dataset.py      manifiesto, split por emisor, anonimización
  sintetica.py    facturas sintéticas para tests y demo
  cli.py          comandos `facturas ...`
docs/decisiones.md  por qué está hecho así
data/README.md      cómo juntar y etiquetar los datos
```

## Uso de IA en el desarrollo

El código se escribió con asistencia de Claude Code. Las decisiones de diseño y sus motivos están en [`docs/decisiones.md`](docs/decisiones.md), y cada módulo tiene tests.
