// Standard desktop Playwright export; no external requests are needed.
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1400, height: 840}});
    await page.route(/^https?:/, route => route.abort());
    await page.goto(pathToFileURL(path.join(__dirname, 'index.html')).href);
    await page.evaluate(() => document.fonts.ready);
    await page.emulateMedia({media: 'print'});
    await page.pdf({path: path.join(__dirname, 'КосмоФАЙР-2_защита.pdf'), printBackground: true, preferCSSPageSize: true});
    console.log('PDF: 12 slides exported.');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error.message); process.exitCode = 1;});
