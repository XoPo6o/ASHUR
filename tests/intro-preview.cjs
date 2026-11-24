const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const out = path.join(process.cwd(), 'artifacts');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const errors = [];

  async function openScene(width, height, label) {
    const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
    page.on('pageerror', error => errors.push(label + ': ' + error.message));
    await page.goto('http://127.0.0.1:4173/index.html', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#world');
    await page.waitForTimeout(700);
    const canvas = await page.locator('#world').evaluate(el => {
      const c = el.getContext('2d');
      const d = c.getImageData(0, 0, el.width, el.height).data;
      let different = 0;
      for (let i = 0; i < d.length; i += 16) {
        if (d[i] !== d[0] || d[i + 1] !== d[1] || d[i + 2] !== d[2]) different++;
      }
      return { width: el.width, height: el.height, different };
    });
    if (canvas.width !== 480 || canvas.height !== 270 || canvas.different < 500) {
      throw new Error(label + ': canvas is blank or has unexpected dimensions: ' + JSON.stringify(canvas));
    }
    return page;
  }

  try {
    const desktop = await openScene(1440, 900, 'desktop');
    await desktop.waitForTimeout(800);
    await desktop.screenshot({ path: path.join(out, '01-market-arrival.png') });
    await desktop.waitForTimeout(8500);
    await desktop.screenshot({ path: path.join(out, '02-fall-and-dust.png') });
    await desktop.waitForTimeout(3800);
    const openingVisible = await desktop.locator('#opening').evaluate(el => getComputedStyle(el).opacity);
    const cuneiformVisible = await desktop.locator('#cuneiform').evaluate(el => getComputedStyle(el).opacity);
    if (Number(openingVisible) < 0.9 || Number(cuneiformVisible) < 0.9) {
      throw new Error('Opening text or cuneiform did not appear at the expected time');
    }
    await desktop.screenshot({ path: path.join(out, '03-cuneiform.png') });
    await desktop.waitForTimeout(3800);
    const titleVisible = await desktop.locator('#game-title').evaluate(el => getComputedStyle(el).opacity);
    if (Number(titleVisible) < 0.9) throw new Error('KI.LAM title did not appear');
    const desktopMark = await desktop.locator('#game-title').evaluate(el => {
      const box = el.getBoundingClientRect();
      const cells = [...el.querySelectorAll('.glyph')].map(node => {
        const r = node.getBoundingClientRect();
        return { x: r.x, y: r.y, width: r.width, height: r.height };
      });
      return { width: box.width, height: box.height, cells };
    });
    if (Math.abs(desktopMark.width - desktopMark.height) > 1 ||
        desktopMark.cells.length !== 6 ||
        Math.abs(desktopMark.cells[0].x - desktopMark.cells[3].x) > 1 ||
        Math.abs(desktopMark.cells[1].x - desktopMark.cells[4].x) > 1 ||
        Math.abs(desktopMark.cells[2].x - desktopMark.cells[5].x) > 1 ||
        Math.abs(desktopMark.cells[0].y - desktopMark.cells[1].y) > 1 ||
        Math.abs(desktopMark.cells[3].y - desktopMark.cells[4].y) > 1) {
      throw new Error('KI.LAM mark is not a square 3x2 grid: ' + JSON.stringify(desktopMark));
    }
    await desktop.screenshot({ path: path.join(out, '04-title-desktop.png') });

    const mobile = await openScene(390, 844, 'mobile');
    await mobile.waitForTimeout(16300);
    const mobileTitle = await mobile.locator('#game-title').evaluate(el => getComputedStyle(el).opacity);
    const titleBox = await mobile.locator('#game-title').boundingBox();
    if (Number(mobileTitle) < 0.9 || !titleBox || titleBox.y < 0 || titleBox.y + titleBox.height > 844) {
      throw new Error('Mobile title is hidden or clipped: ' + JSON.stringify({ mobileTitle, titleBox }));
    }
    const mobileMark = await mobile.locator('#game-title').boundingBox();
    if (!mobileMark || Math.abs(mobileMark.width - mobileMark.height) > 1) {
      throw new Error('Mobile KI.LAM mark is not square: ' + JSON.stringify(mobileMark));
    }
    await mobile.screenshot({ path: path.join(out, '05-title-mobile.png'), fullPage: true });

    const landscape = await openScene(844, 390, 'mobile-landscape');
    const landscapeBox = await landscape.locator('#world').boundingBox();
    if (!landscapeBox || landscapeBox.x < -1 || landscapeBox.x + landscapeBox.width > 845) {
      throw new Error('Landscape scene is horizontally clipped: ' + JSON.stringify(landscapeBox));
    }
    await landscape.screenshot({ path: path.join(out, '06-title-landscape.png') });

    const skipPage = await openScene(390, 844, 'touch-skip');
    await skipPage.mouse.click(195, 420);
    await skipPage.waitForTimeout(900);
    const skippedTitle = await skipPage.locator('#game-title').evaluate(el => getComputedStyle(el).opacity);
    if (Number(skippedTitle) < 0.9) throw new Error('Touch skip did not reveal the title');
    if (errors.length) throw new Error('Browser runtime errors: ' + errors.join(' | '));
    console.log('INTRO_VISUAL_TEST_OK', JSON.stringify({ openingVisible, cuneiformVisible, titleVisible, desktopMark, mobileTitle, titleBox, mobileMark, landscapeBox, skippedTitle, errors }));
  } finally {
    await browser.close();
  }
})();
