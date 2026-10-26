// Captura un HTML local como PNG (o PDF de una página).
// Uso: node captura.cjs <entrada.html> <salida.png|pdf> <ancho> <alto> [escala]
const { chromium } = require('playwright');
const { pathToFileURL } = require('node:url');
const path = require('node:path');

(async () => {
  const [entrada, salida, ancho, alto, escala] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: Number(ancho), height: Number(alto) },
    deviceScaleFactor: Number(escala || 1),
  });
  await page.goto(pathToFileURL(path.resolve(entrada)).href, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  if (salida.endsWith('.pdf')) {
    await page.pdf({ path: salida, format: 'A4', printBackground: true, margin: { top: '0', right: '0', bottom: '0', left: '0' }, preferCSSPageSize: true });
  } else {
    await page.screenshot({ path: salida, fullPage: false });
  }
  await browser.close();
  console.log('Generado:', salida);
})();
