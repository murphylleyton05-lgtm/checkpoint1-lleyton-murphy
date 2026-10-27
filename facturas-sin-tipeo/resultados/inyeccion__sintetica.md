# Errores inyectados: qué detectan las reglas (origen sintetica, 40 facturas base)

Facturas base descartadas por tener ya un error: 0

«Detectados con QR» se calcula solo sobre las facturas base que tienen QR.

| Error inyectado | Casos | Detectados sin QR | Detectados con QR |
|---|---|---|---|
| `cuit_un_digito` | 40 | 100% | 100% |
| `cuit_transposicion` | 40 | 100% | 100% |
| `total_alterado` | 40 | 50% | 100% |
| `iva_alterado` | 30 | 67% | 67% |
| `alicuota_inexistente` | 30 | 100% | 100% |
| `numero_corrido` | 40 | 0% | 100% |
| `punto_venta_corrido` | 40 | 0% | 100% |
| `letra_equivocada` | 40 | 0% | 100% |
| `fecha_futura` | 40 | 100% | 100% |
| `fecha_dia_mes_invertidos` | 11 | 27% | 100% |
| `cae_truncado` | 40 | 100% | 100% |
