# Datos: protocolo de recolección y etiquetado

Nada de esta carpeta se sube al repositorio, salvo este archivo, `etiquetas/EJEMPLO.json` y la plantilla `baseline_manual.csv` (ver `.gitignore`). Los PDFs tienen datos de personas y empresas reales.

## 1. Qué juntar

- **Meta: ≥ 100 comprobantes electrónicos reales de ≥ 15 emisores distintos.** Con menos emisores, el test mide cuánto se aprendió el diseño de pocos proveedores.
- Mezcla de tipos: facturas A, B y C y, si aparecen, notas de crédito.
- Fuentes posibles: tus facturas (luz, gas, internet, telefonía, prepaga, compras online) y las de familiares o de una PyME conocida **con su consentimiento por escrito** (un mensaje alcanza). Anotá de dónde vino cada lote.
- Si aparecen comprobantes sin QR (viejos o escaneados), sumalos: muestran qué pasa cuando no hay verificación.

## 2. Cómo cargarlos

```bash
# Una carpeta por origen
data/crudas/propias/*.pdf
data/crudas/familia/*.pdf

facturas registrar --entrada data/crudas/propias --origen propia
facturas registrar --entrada data/crudas/familia --origen familiar
```

`registrar` lee el QR de cada PDF nuevo, guarda la referencia en `data/referencia/` y agrega el documento a `data/manifiesto.csv` con su split. Volver a correrlo no duplica nada.

## 3. Split dev/test (congelado)

- El 30 % de los **emisores** va a test; todas las facturas de un mismo emisor quedan del mismo lado.
- **Iterá el prompt solo con `dev`.** El test se corre una vez por cada versión de prompt que vayas a reportar. Si mirás los errores del test y ajustás el prompt en base a ellos, el número del test deja de valer.

## 4. Etiquetas manuales (30 documentos: 15 de dev y 15 de test)

El QR no trae IVA, netos ni ítems. Para medir esos campos:

1. Copiá `etiquetas/EJEMPLO.json` a `etiquetas/<doc_id>.json` (el `doc_id` está en el manifiesto).
2. Completá **solo los campos que verificaste mirando el PDF**. Si un campo no está impreso, poné `null`. Si no lo revisaste, borralo: se mide únicamente lo que la etiqueta trae.
3. Las reglas de transcripción son las mismas que se le piden al modelo (ver `SISTEMA` en `src/facturas/extraccion.py`). Por ejemplo, en un B que solo informa «IVA contenido», el neto va en `null`.

## 5. Baseline manual cronometrado

Antes de mirar resultados del modelo, cargá a mano 20 facturas en una planilla con los campos del encabezado + IVA, como lo haría un administrativo. Cronometrá cada una y anotala en `baseline_manual.csv`:

```
doc_id,segundos,notas
1b02bd2ecae4,95,factura de 3 páginas
```

Este número es el «antes» del proyecto: sin él no se puede decir cuánto tiempo ahorra el sistema.
