# Ingresos variables, sueldo fijo — producto digital completo

Ebook + bonos + kit comercial para vender en Shopify. Nicho: finanzas personales para personas con ingresos variables (freelancers, autónomos, monotributistas, independientes hispanohablantes).

## Entregables (`entregables/`)

| Archivo | Qué es |
|---|---|
| `Ingresos-variables-sueldo-fijo.pdf` | El ebook (128 páginas, A4, con índice paginado y marcadores). |
| `Plantilla-Metodo-Embalse.xlsx` | Bono: plantilla de cálculo en blanco (Excel / Google Sheets). |
| `Plantilla-Metodo-Embalse-EJEMPLO.xlsx` | Bono: la misma plantilla con el caso hipotético de Valeria. |
| `Bono-Cuaderno-de-trabajo.pdf` | Bono: hojas de trabajo y checklists imprimibles. |
| `Bono-Mapa-del-Metodo-Embalse.pdf` | Bono e imán de suscriptores: el método en una página. |
| `Kit-comercial-y-plan-de-lanzamiento.pdf` | Investigación de mercado, producto, precios, Shopify, landing, plan de 30 días, contenido, proyecciones, riesgos y control de calidad. |
| `imagenes/` | 6 imágenes para la tienda y redes (portada, mockups, interior, plantilla, pin de Pinterest). |

## Cómo regenerar todo

Requisitos: Python 3 con `openpyxl` y `pypdf`, Node con Playwright (Chromium), LibreOffice y `pdftoppm`.

```bash
python3 herramientas/crear_plantilla.py   # planillas XLSX
python3 herramientas/construir_ebook.py   # gráficos + ebook PDF (índice paginado en dos pasadas)
python3 herramientas/crear_mockups.py     # imágenes + bonos PDF (usa el ebook ya generado)
python3 herramientas/construir_kit.py     # kit comercial PDF
```

## Dónde editar

- Texto del libro: `fuente/partes/*.html` (se unen en orden alfabético). Estilos: `fuente/estilos.css`. Portada: `fuente/portada.html`.
- Nombre del autor: `fuente/portada.html`, `fuente/partes/00-legal.html`, `herramientas/construir_ebook.py` (y la portada del kit).
- Gráficos: `herramientas/graficos.py` (datos de los casos).
- Kit comercial: `comercial/partes/*.html`.

## Avisos

- Material educativo: no es asesoramiento financiero, fiscal ni de inversión. Los casos son hipotéticos.
- Antes de vender: lectura y corrección humana, revisión del capítulo 5 y del Anexo C por un contador, y verificación de planes, comisiones y medios de pago de Shopify para tu país (ver la sección 15 del kit).
- Tipografías incluidas bajo SIL Open Font License (`fuente/fuentes-tipograficas/`).
