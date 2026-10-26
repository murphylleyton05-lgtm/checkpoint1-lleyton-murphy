// Renderiza un HTML local a PDF con Chromium (Playwright).
// Uso: node render.cjs <entrada.html> <salida.pdf> [--portada] [--pie "Texto del pie"]
const { chromium } = require('playwright');
const { pathToFileURL } = require('node:url');
const path = require('node:path');

const args = process.argv.slice(2);
const [entrada, salida] = args;
const esPortada = args.includes('--portada');
const iPie = args.indexOf('--pie');
const textoPie = iPie >= 0 ? args[iPie + 1] : '';

if (!entrada || !salida) {
  console.error('Uso: node render.cjs <entrada.html> <salida.pdf> [--portada] [--pie "texto"]');
  process.exit(1);
}

(async () => {
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(pathToFileURL(path.resolve(entrada)).href, { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts.ready);

const opciones = esPortada
  ? { path: salida, format: 'A4', printBackground: true, margin: { top: '0', right: '0', bottom: '0', left: '0' }, preferCSSPageSize: true }
  : {
      path: salida,
      format: 'A4',
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: '<div></div>',
      footerTemplate: `
        <div style="width:100%; font-family: Inter, Arial, sans-serif; font-size:7.6pt; color:#5f6f77; padding:0 24mm; display:flex; justify-content:space-between; align-items:center;">
          <span style="letter-spacing:0.04em;">${textoPie}</span>
          <span class="pageNumber" style="font-weight:600; color:#0e3a4a;"></span>
        </div>`,
      margin: { top: '20mm', right: '24mm', bottom: '20mm', left: '24mm' },
    };

await page.pdf(opciones);
await browser.close();
console.log('PDF generado:', salida);
})();
