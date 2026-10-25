// Exporta una composicion del lienzo con Chromium: PNG (1x o 2x) o PDF con texto vectorial.
// uso: node render.mjs <url> <destino> <png|pdf> <w> <h> <escala>
import { chromium } from "playwright";

const [url, destino, fmt, w, h, escala] = process.argv.slice(2);
const W = +w, H = +h;
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: +escala || 1 });
  const errores = [];
  page.on("pageerror", e => errores.push(e.message));
  await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
  // el lienzo avisa cuando cargo fuentes, imagenes y termino de ajustar los textos
  await page.waitForFunction(() => window.__listo === true, null, { timeout: 60000 });
  if (errores.length) throw new Error(errores.join(" | "));
  // el informe del juez sale por stdout: el motor lo lee para auto-corregir
  console.log("JUEZ " + JSON.stringify(await page.evaluate(() => window.__juez || null)));
  if (fmt === "pdf") {
    await page.pdf({ path: destino, width: `${W}px`, height: `${H}px`, printBackground: true, pageRanges: "1" });
  } else {
    await page.screenshot({ path: destino, clip: { x: 0, y: 0, width: W, height: H }, omitBackground: true });
  }
} finally {
  await browser.close();
}
