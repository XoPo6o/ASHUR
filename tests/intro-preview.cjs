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
    if (canvas.width !== 320 || canvas.height !== 224 || canvas.different < 500) {
      throw new Error(label + ': canvas is blank or has unexpected dimensions: ' + JSON.stringify(canvas));
    }
    return page;
  }

  try {
    const desktop = await openScene(1440, 900, 'desktop');
    await desktop.waitForTimeout(800);
    await desktop.screenshot({ path: path.join(out, '01-market-arrival.png') });
    await desktop.waitForTimeout(8500);
    const reaction = await desktop.locator('#world').evaluate(el => el.dataset.observerReaction);
    if (reaction !== 'true') throw new Error('Observers did not enter their reaction state after the fall');
    await desktop.screenshot({ path: path.join(out, '02-fall-and-observers.png') });

    await desktop.waitForTimeout(1600);
    const openingPhase = await desktop.locator('#opening').evaluate(el => Number(getComputedStyle(el).opacity));
    const cuneiformBefore = await desktop.locator('#cuneiform').evaluate(el => Number(getComputedStyle(el).opacity));
    if (openingPhase < 0.9 || cuneiformBefore > 0.1) {
      throw new Error('Opening phrase phase is not isolated: ' + JSON.stringify({ openingPhase, cuneiformBefore }));
    }
    await desktop.screenshot({ path: path.join(out, '03-opening-phrase.png') });

    await desktop.waitForTimeout(2500);
    const openingHidden = await desktop.locator('#opening').evaluate(el => Number(getComputedStyle(el).opacity));
    const cuneiformVisible = await desktop.locator('#cuneiform').evaluate(el => Number(getComputedStyle(el).opacity));
    if (openingHidden > 0.1 || cuneiformVisible < 0.9) {
      throw new Error('Opening phrase did not disappear before cuneiform: ' + JSON.stringify({ openingHidden, cuneiformVisible }));
    }
    await desktop.screenshot({ path: path.join(out, '04-cuneiform.png') });

    await desktop.waitForTimeout(3500);
    const titleVisible = await desktop.locator('#game-title').evaluate(el => Number(getComputedStyle(el).opacity));
    if (titleVisible < 0.9) throw new Error('KI.LAM title did not appear');
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
        Math.abs(desktopMark.cells[0].y - desktopMark.cells[2].y) > 1 ||
        Math.abs(desktopMark.cells[3].y - desktopMark.cells[4].y) > 1 ||
        Math.abs(desktopMark.cells[3].y - desktopMark.cells[5].y) > 1 ||
        desktopMark.cells.some(cell => Math.abs(cell.width - desktopMark.width / 3) > 1 ||
          Math.abs(cell.height - desktopMark.height / 2) > 1)) {
      throw new Error('KI.LAM mark is not a square 3x2 grid: ' + JSON.stringify(desktopMark));
    }
    await desktop.screenshot({ path: path.join(out, '05-title-desktop.png') });

    const mobile = await openScene(390, 844, 'mobile');
    await mobile.waitForTimeout(9000);
    const mobileCamera = await mobile.locator('#world').evaluate(el => Number(el.dataset.cameraX));
    const mobileReaction = await mobile.locator('#world').evaluate(el => el.dataset.observerReaction);
    const mobileFrame = await mobile.locator('#world').evaluate(el => {
      const r = el.getBoundingClientRect();
      return { objectFit: getComputedStyle(el).objectFit, width: r.width, height: r.height };
    });
    if (!(mobileCamera > 0) || mobileReaction !== 'true' ||
        mobileFrame.objectFit !== 'cover' || mobileFrame.width !== 390 || mobileFrame.height !== 844) {
      throw new Error('Portrait camera, fall reaction or full-screen framing failed: ' +
        JSON.stringify({ mobileCamera, mobileReaction, mobileFrame }));
    }
    await mobile.screenshot({ path: path.join(out, '06-mobile-fall-follow.png') });
    await mobile.waitForTimeout(8000);
    const mobileTitle = await mobile.locator('#game-title').evaluate(el => getComputedStyle(el).opacity);
    const titleBox = await mobile.locator('#game-title').boundingBox();
    if (Number(mobileTitle) < 0.9 || !titleBox || titleBox.y < 0 || titleBox.y + titleBox.height > 844) {
      throw new Error('Mobile title is hidden or clipped: ' + JSON.stringify({ mobileTitle, titleBox }));
    }
    const mobileMark = await mobile.locator('#game-title').boundingBox();
    if (!mobileMark || Math.abs(mobileMark.width - mobileMark.height) > 1) {
      throw new Error('Mobile KI.LAM mark is not square: ' + JSON.stringify(mobileMark));
    }
    await mobile.screenshot({ path: path.join(out, '07-title-mobile.png'), fullPage: true });

    const landscape = await openScene(844, 390, 'mobile-landscape');
    await landscape.waitForTimeout(16800);
    const landscapeBox = await landscape.locator('#world').boundingBox();
    const landscapeTitle = await landscape.locator('#game-title').evaluate(el => getComputedStyle(el).opacity);
    const landscapeTitleBox = await landscape.locator('#game-title').boundingBox();
    if (!landscapeBox || landscapeBox.x < -1 || landscapeBox.x + landscapeBox.width > 845 ||
        Number(landscapeTitle) < 0.9 || !landscapeTitleBox ||
        landscapeTitleBox.y < 0 || landscapeTitleBox.y + landscapeTitleBox.height > 390) {
      throw new Error('Landscape scene or title is clipped: ' + JSON.stringify({ landscapeBox, landscapeTitle, landscapeTitleBox }));
    }
    await landscape.screenshot({ path: path.join(out, '08-title-landscape.png') });

    const skipPage = await openScene(390, 844, 'touch-skip');
    await skipPage.mouse.click(195, 420);
    await skipPage.waitForTimeout(900);
    const skippedTitle = await skipPage.locator('#game-title').evaluate(el => getComputedStyle(el).opacity);
    const skippedOpening = await skipPage.locator('#opening').evaluate(el => Number(getComputedStyle(el).opacity));
    if (Number(skippedTitle) < 0.9 || skippedOpening > 0.1) throw new Error('Touch skip did not reveal a clean final title card');
    const palette = await desktop.locator('#world').evaluate(el => {
      const d = el.getContext('2d').getImageData(0, 0, 320, 224).data;
      const colors = new Set();
      for (let i = 0; i < d.length; i += 4) colors.add((d[i] << 16) | (d[i + 1] << 8) | d[i + 2]);
      return colors.size;
    });
    if (palette > 60) throw new Error('Frame exceeds the 4x15 visible-color budget: ' + palette);
        if (errors.length) throw new Error('Browser runtime errors: ' + errors.join(' | '));
    console.log('INTRO_VISUAL_TEST_OK', JSON.stringify({ openingPhase, openingHidden, cuneiformVisible, titleVisible, desktopMark, mobileTitle, titleBox, mobileMark, landscapeBox, skippedTitle, skippedOpening, mobileCamera, mobileReaction, mobileFrame, palette, errors }));
  } finally {
    await browser.close();
  }
})();
