# Registro de decisiones

Cada entrada dice qué se decidió, por qué y qué se descartó. Si una decisión cambia, se agrega una entrada nueva en vez de editar la vieja.

---

### D1. El QR fiscal es la referencia de evaluación del encabezado

**Contexto.** Medir la extracción exige saber la respuesta correcta. Etiquetar 100 facturas a mano lleva horas y mete mis propios errores en la referencia.

**Decisión.** Los comprobantes electrónicos traen un QR (RG 4892) con CUIT del emisor, punto de venta, tipo, número, fecha, importe total, moneda, documento del receptor y CAE. Ese QR lo genera el sistema del emisor, así que es una referencia independiente del modelo y de mí.

**Descartado.** Etiquetar todo a mano (caro y sesgado). Usar un segundo LLM como juez (mide acuerdo entre modelos, no exactitud).

**Consecuencia.** El QR no trae IVA, netos ni ítems: para esos campos hace falta una muestra chica etiquetada a mano (D5).

### D2. El modelo nunca recibe el contenido del QR

Si el prompt incluyera los datos del QR, la medición contra el QR sería circular. En modo `pdf` el modelo ve la imagen del QR, pero no la decodifica: lo que transcribe sale del texto impreso.

### D3. Split dev/test por emisor y congelado

Las facturas de un mismo proveedor tienen el mismo diseño. Con un split por documento, el prompt podría ajustarse a los diseños vistos en dev y el test mediría memoria. El split se asigna por hash del CUIT del emisor (30 % a test) y queda guardado en el manifiesto: agregar documentos no mueve los existentes.

### D4. La revisión humana la deciden reglas deterministas, no la confianza del LLM

La «confianza» que un LLM declara sobre su propia respuesta no está calibrada. Una regla (dígito verificador del CUIT, neto + IVA = total, coincidencia con el QR) falla por un motivo explicable y testeable. Un documento va a revisión si dispara al menos una regla de severidad `error`.

### D5. Tres mediciones separadas para no hacerse trampa

La regla `coincide_con_qr` usa el mismo QR que la medición de exactitud, así que «lo aprobado coincide con el QR» es cierto por construcción. Por eso se reporta por separado:

1. Exactitud del LLM contra el QR (sin reglas de por medio).
2. Error residual en lo aprobado automáticamente, medido **solo con etiquetas manuales** en campos que el QR no cubre.
3. Qué errores del LLM detectan las reglas **sin mirar el QR** (el caso de un documento sin QR).

### D6. Una extracción fallida cuenta como error en todos sus campos

Descartar los documentos donde la API falló o la respuesta no respetó el esquema inflaría la exactitud justo con los casos difíciles.

### D7. Toda tasa va con intervalo de Wilson al 95 %

Con 100 documentos, 97 % de aciertos es compatible con valores entre ~91,5 % y ~99 %. Reportar el punto sin el intervalo da una precisión falsa.

### D8. JSON del QR cortado: se descarta el último campo

En facturas reales aparecen QR con el JSON truncado. El último campo puede estar cortado a la mitad (`"tipoDocRec": 8` en vez de 80), así que se recorta hasta la última coma completa y el documento queda marcado como `qr_reparado`. Se descartó usar una librería de «reparación» de JSON, porque completaría el valor truncado como si fuera bueno.

### D9. CUIT, CAE y documento se comparan sin ceros a la izquierda

El QR guarda esos campos como número JSON, que pierde los ceros iniciales. Lo detectó un test con un CAE sintético que empezaba con 0.

### D10. Un B que solo informa «IVA contenido» no bloquea por totales

Si el comprobante no imprime el neto, el modelo tiene que devolver `null` en vez de calcularlo, y entonces no hay con qué reconstruir el total. La regla avisa (advertencia) pero no bloquea; bloquear mandaría a revisión casi todos los B por una limitación del documento, no por un error.

### D11. Lectura de QR con el detector Aruco de OpenCV y las imágenes embebidas primero

Con 5 sintéticas renderizadas a 2x, el detector clásico de OpenCV no decodificó 2; el detector Aruco las leyó todas desde 2x. La primera versión, además, tenía un bug: si el detector múltiple encontraba el QR pero no lo decodificaba, no se probaba el detector simple. Ahora se prueba primero la imagen embebida, a su resolución original, y después la página renderizada a 2x, 3x y 4x. En 60 sintéticas leyó 60. Falta medirlo con PDFs reales, que son más variados.

### D12. Los documentos no salen de la máquina salvo hacia la API

`data/` está fuera de git. Los reportes que se suben son agregados. El detalle por documento queda local, con el documento del receptor anonimizado con sal.

### D13. Fallback automático del lado del servidor en Opus y Sonnet

Si el modelo rechaza un pedido por un falso positivo de sus filtros, la API lo re-ejecuta en otro modelo (`fallbacks: "default"`). Queda registrado qué modelo respondió (`modelo_servido`) y el costo se calcula con el precio de ese modelo. Haiku no tiene fallback del lado del servidor.

---

## Hallazgos de la inyección de errores (facturas sintéticas)

Al inyectar errores típicos en 40 facturas sintéticas correctas (`facturas inyectar`):

- **Sin QR, las reglas no ven** un número de comprobante o un punto de venta corrido, ni una letra cambiada (A↔B). El QR es la única defensa contra esos errores.
- **El IVA de un B no se puede verificar ni con QR:** el QR no trae IVA y, sin neto impreso, no hay con qué compararlo. Es el principal motivo de las etiquetas manuales.
- Un total alterado se detecta sin QR solo cuando el comprobante imprime los netos (A), no en B o C.

Pendiente: repetir con facturas reales y decidir si vale la pena una regla de padrón (consultar la condición frente al IVA del receptor) para atrapar letras equivocadas sin QR.
