/* Local portfolio visual review. Uses the loopback application and catalog only. */
const { chromium } = require('./browser/node_modules/playwright');
const AxeBuilder = require('./browser/node_modules/@axe-core/playwright').default;
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.SHOPSMART_BASE_URL || 'http://127.0.0.1:3000';
const output = path.resolve('docs/portfolio/screenshots');
const report = { viewportChecks: [], journeys: [], accessibility: [], errors: [] };

async function settle(page) {
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  await page.evaluate(() => { document.querySelectorAll('img').forEach((image) => { image.loading = 'eager'; }); });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.race([
      Promise.all([...document.images].map((image) => image.decode().catch(() => {}))),
      new Promise((resolve) => setTimeout(resolve, 4000)),
    ]);
  });
}

async function capture(page, file, fullPage = false) {
  await settle(page);
  if (file.startsWith('assistant-') && fullPage) {
    await page.addStyleTag({ content: 'form.sticky, header, nav { position: static !important; }' });
  }
  await page.screenshot({ path: path.join(output, file), fullPage });
}

async function enterScene(page, number) {
  await page.getByRole('button', { name: new RegExp('Scene ' + number + ':') }).click();
  await page.waitForTimeout(250);
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  page.on('pageerror', (error) => report.errors.push(error.message));

  await page.goto(base);
  await page.getByRole('button', { name: 'Scene 2: Your brief' }).waitFor();
  await capture(page, 'hero-opening-1440.png');
  report.journeys.push({ name: 'Editorial product opening from the live catalog', passed: true });

  const states = [
    [2, 'hero-intent-1440.png'],
    [3, 'hero-discovery-1440.png'],
    [4, 'hero-comparison-1440.png'],
    [5, 'hero-recommendation-1440.png'],
    [6, 'hero-purchase-1440.png'],
  ];
  for (const [scene, file] of states) {
    await enterScene(page, scene);
    await capture(page, file);
    if (scene === 3) {
      const count = (await page.locator('[class*="candidateHeading"] b').first().innerText()).trim();
      if (!count.startsWith('03')) throw new Error(`Expected 3 in-budget candidates in the hero, received ${count}`);
    }
    report.journeys.push({ name: 'Hero scene ' + scene, passed: await page.getByRole('button', { name: new RegExp('Scene ' + scene + ':') }).getAttribute('aria-current') === 'step' });
  }

  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto(base);
  await page.getByRole('button', { name: 'Scene 2: Your brief' }).waitFor();
  await capture(page, 'hero-opening-1024.png');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base);
  await page.getByRole('button', { name: 'Scene 2: Your brief' }).waitFor();
  await capture(page, 'hero-opening-390.png');
  await enterScene(page, 3);
  await capture(page, 'hero-discovery-390.png');

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base);
  await page.getByRole('button', { name: 'Scene 2: Your brief' }).waitFor();
  await capture(page, 'hero-reduced-motion-1440.png');
  const motion = await page.locator('section[aria-labelledby="hero-heading"]').evaluate((node) => {
    const stage = node.querySelector('[class*="productStage"]');
    return stage ? getComputedStyle(stage).animationName : '';
  });
  report.journeys.push({ name: 'Reduced motion hero', passed: motion === 'none', animationName: motion });
  report.accessibility.push({
    route: '/',
    mode: 'mobile reduced motion',
    violations: (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target) })),
  });

  await page.emulateMedia({ reducedMotion: 'no-preference' });
  for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    for (const route of ['/', '/products?category=laptops']) {
      await page.goto(base + route);
      await settle(page);
      const measured = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth, height: innerHeight }));
      report.viewportChecks.push({ route, requested: viewport, ...measured, passed: measured.width === viewport.width && measured.scrollWidth <= measured.width });
      if (route.startsWith('/products')) await capture(page, 'catalog-' + viewport.width + '.png', true);
    }
  }

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base + '/products?category=laptops');
  await settle(page);
  await capture(page, 'catalog-desktop.png', true);
  await page.locator('a[href^="/products/"]').first().click();
  await page.getByRole('heading', { level: 1 }).waitFor();
  await capture(page, 'pdp-desktop.png', true);
  await page.setViewportSize({ width: 390, height: 844 });
  await capture(page, 'pdp-mobile.png', true);

  const testEmail = `visual-review-${Date.now()}@example.test`;
  const testPassword = 'PortfolioOnly!2026';
  const registered = await page.request.post(base + '/api/auth/register', { data: { email: testEmail, password: testPassword } });
  if (!registered.ok()) throw new Error('Could not create the disposable assistant review account: ' + await registered.text());
  const loggedIn = await page.request.post(base + '/api/auth/login', { data: { email: testEmail, password: testPassword } });
  if (!loggedIn.ok()) throw new Error('Could not sign in to the disposable assistant review account: ' + await loggedIn.text());
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base + '/assistant?q=' + encodeURIComponent('Find laptops under \u20b970,000'));
  await page.getByRole('textbox', { name: 'Message the shopping assistant' }).waitFor();
  await capture(page, 'assistant-prompt-desktop.png', true);
  const assistantResponse = page.waitForResponse((response) => response.url().includes('/api/ai/chat') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Send' }).click();
  const response = await assistantResponse;
  if (!response.ok()) throw new Error(`Assistant returned HTTP ${response.status()}`);
  const searchResult = await response.json();
  if (searchResult.intent !== 'PRODUCT_SEARCH' || !searchResult.result_data?.products?.length) throw new Error('Assistant did not return grounded catalog products');
  report.journeys.push({ name: 'Assistant catalog search results', passed: true, products: searchResult.result_data.products.length });
  await page.locator('article').nth(1).waitFor({ timeout: 30000 });
  await capture(page, 'assistant-results-desktop.png', true);
  await page.getByRole('textbox', { name: 'Message the shopping assistant' }).fill('Which of these is best for React development?');
  const adviceResponse = page.waitForResponse((item) => item.url().includes('/api/ai/chat') && item.request().method() === 'POST');
  await page.getByRole('button', { name: 'Send' }).click();
  const advice = await adviceResponse;
  if (!advice.ok()) throw new Error(`Assistant recommendation returned HTTP ${advice.status()}`);
  const adviceResult = await advice.json();
  if (adviceResult.intent !== 'PRODUCT_ADVICE' || !adviceResult.result_data?.products?.length) throw new Error('Assistant did not return a grounded recommendation');
  report.journeys.push({ name: 'Assistant product advice from search results', passed: true, products: adviceResult.result_data.products.length });
  await page.locator('article').nth(3).waitFor({ timeout: 30000 });
  await capture(page, 'assistant-recommendation-desktop.png', true);
  await page.setViewportSize({ width: 390, height: 844 });
  await capture(page, 'assistant-results-mobile.png', true);

  fs.writeFileSync('.factory/runtime/browser-report.json', JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
})().catch((error) => {
  console.error(error);
  fs.writeFileSync('.factory/runtime/browser-report.json', JSON.stringify({ ...report, failure: error.message }, null, 2));
  process.exitCode = 1;
});
