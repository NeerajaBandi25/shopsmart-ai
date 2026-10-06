import { test, expect, Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Uses disposable review DB accounts supplied through environment, never a production account.
test.beforeEach(async ({ page }, testInfo) => {
  const email =
    process.env[`E2E_EMAIL_${testInfo.project.name.toUpperCase()}`] ?? process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  if (!email || !password)
    throw new Error('Set E2E_EMAIL/E2E_PASSWORD for the isolated review database.');
  await page.goto('/auth/login?redirectTo=/assistant');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Log In', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Shopping assistant', exact: true })
  ).toBeVisible();
  await page.goto('/cart');
  const cleared = await page.evaluate(async () => {
    const csrfResponse = await fetch('/api/auth/csrf', { credentials: 'include' });
    if (!csrfResponse.ok) throw new Error(`CSRF request returned ${csrfResponse.status}`);
    const { csrf_token: csrfToken } = await csrfResponse.json();
    const cartResponse = await fetch('/api/cart', { credentials: 'include' });
    if (!cartResponse.ok) throw new Error(`Cart request returned ${cartResponse.status}`);
    const cart = await cartResponse.json();
    for (const item of cart.items) {
      const response = await fetch(`/api/cart/items/${encodeURIComponent(item.product_id)}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      if (!response.ok) throw new Error(`Cart item cleanup returned ${response.status}`);
    }
    if (cart.coupon_code) {
      const response = await fetch('/api/cart/coupon', {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      if (!response.ok) throw new Error(`Coupon cleanup returned ${response.status}`);
    }
    return true;
  });
  expect(cleared).toBe(true);
  await page.reload();
  await expect(page.getByText('Your cart is empty.', { exact: true })).toBeVisible();
  await page.goto('/assistant');
  await expect(
    page.getByRole('heading', { name: 'Shopping assistant', exact: true })
  ).toBeVisible();
  await page.getByRole('button', { name: 'New chat', exact: true }).click();
});

async function ask(page: Page, question: string) {
  const responseCount = await page.getByText('ShopSmart assistant', { exact: true }).count();
  await page.getByLabel('Message the shopping assistant').fill(question);
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'New chat', exact: true })).toBeEnabled();
  await expect(page.getByText('ShopSmart assistant', { exact: true })).toHaveCount(
    responseCount + 1
  );
}

test('real shopping mission, evidence, refinement, cart, offers, policy and orders', async ({
  page,
}) => {
  const errors: string[] = [];
  const failedRequests: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('requestfailed', (request) => {
    if (request.failure()?.errorText !== 'net::ERR_ABORTED') {
      failedRequests.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText}`);
    }
  });
  page.on('response', (response) => {
    if (response.status() >= 400) {
      failedRequests.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  await ask(
    page,
    'I am a developer using React, Python and Docker. I occasionally run local AI models. I commute often and prefer something professional-looking. I prefer around ₹75,000 but can stretch to ₹85,000 if worthwhile.'
  );
  await expect(
    page.getByRole('group', { name: 'Shopping mission', exact: true }).last()
  ).toBeVisible();
  const initialResults = page.getByRole('group', { name: 'Product results', exact: true }).last();
  await expect(initialResults).toBeVisible();
  const recommendedName = (
    await initialResults.locator('article h3').first().textContent()
  )?.trim();
  expect(recommendedName).toBeTruthy();
  await expect(page.getByText(/\/100 mission fit/).first()).toBeVisible();
  await expect(page.getByText('Why it fits', { exact: true }).first()).toBeVisible();
  await page.getByText('Why this ranking?', { exact: true }).first().click();
  await expect(page.getByText(/Scores reflect this mission/).first()).toBeVisible();
  await ask(page, 'Only show lighter options.');
  const weightReply = page.locator('article').filter({ hasText: 'ShopSmart assistant' }).last();
  await expect(weightReply).toContainText(/can't verify which options are lighter/i);
  await expect(weightReply).toContainText("aren't confirmed by weight");
  await ask(page, 'Compare the first two.');
  await expect(
    page.getByRole('table', { name: 'Catalog fields returned for these products' }).last()
  ).toBeVisible();
  await ask(page, 'Which one is better for local AI?');
  await ask(page, 'Is spending the extra money actually worth it?');
  await ask(page, 'Add your recommended one.');
  await ask(page, "What's in my cart?");
  await expect(page.getByText(/Subtotal/).last()).toBeVisible();
  const cartLine = page.locator('p').filter({ hasText: recommendedName! }).last();
  await expect(cartLine).toBeVisible();
  await expect
    .poll(async () => (await cartLine.textContent())?.trim() ?? '')
    .toMatch(/^1\s*\u00d7/);
  const updatedCart = await page.evaluate(async () => {
    const response = await fetch('/api/cart', { credentials: 'include' });
    if (!response.ok) throw new Error(`Cart API returned ${response.status}`);
    return response.json();
  });
  const recommendedItem = updatedCart.items.find(
    (item: { name: string }) => item.name === recommendedName
  );
  expect(recommendedItem?.quantity).toBe(1);
  expect(recommendedItem?.unit_price).toBeGreaterThan(0);
  await ask(page, 'Any offers?');
  await expect(page.getByRole('list', { name: 'Promotion results' }).last()).toBeVisible();
  const cartBeforeCoupon = await page.evaluate(async () => {
    const response = await fetch('/api/cart', { credentials: 'include' });
    if (!response.ok) throw new Error(`Cart API returned ${response.status}`);
    return response.json();
  });
  await ask(page, 'Apply SAVE20.');
  await expect(
    page.getByText(/coupon was checked against your cart|Eligible coupon:/i).last()
  ).toBeVisible();
  const couponCart = await page.evaluate(async () => {
    const response = await fetch('/api/cart', { credentials: 'include' });
    if (!response.ok) throw new Error(`Cart API returned ${response.status}`);
    return response.json();
  });
  expect(couponCart.coupon_code).toBe('SAVE20');
  expect(couponCart.coupon_evaluation?.eligible).toBe(true);
  expect(couponCart.discount_total_cents).toBeGreaterThan(0);
  expect(couponCart.total_cents).toBe(couponCart.subtotal - couponCart.discount_total_cents);
  expect(couponCart.discount_total_cents).toBeGreaterThanOrEqual(
    couponCart.coupon_evaluation.discount_cents
  );
  expect(cartBeforeCoupon.total_cents).toBeGreaterThanOrEqual(couponCart.total_cents);
  await ask(page, 'What is your return policy?');
  await expect(page.getByText(/Source:/).last()).toBeVisible();
  await ask(page, 'Where is my latest order?');
  await expect(page.getByText('ShopSmart assistant', { exact: true })).toHaveCount(11);
  expect(errors).toEqual([]);
  expect(failedRequests).toEqual([]);
  const accessibility = await new AxeBuilder({ page }).include('main').analyze();
  expect(accessibility.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true
  );
});

test('explicit preference save, reload and deletion', async ({ page }) => {
  await page.getByRole('button', { name: 'Shopping preferences', exact: true }).click();
  await page.getByLabel('preferred brands (comma separated)').fill('Vellune, Orbiant');
  await page.getByLabel('Preferred budget (₹)').fill('75000');
  await page.getByRole('button', { name: 'Save preferences', exact: true }).click();
  await expect(page.getByText('Your preferences were saved.', { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Shopping preferences', exact: true }).click();
  await expect(page.getByLabel('Preferred budget (₹)')).toHaveValue('75000');
  await page.getByRole('button', { name: 'Clear preferences', exact: true }).click();
  await expect(page.getByText('Your preferences were cleared.', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Preferred budget (₹)')).toHaveValue('');
});

test('home, category search, product, comparison, cart and checkout routes', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('region', { name: 'ShopSmart AI shopping story' })).toBeVisible();
  await page.goto('/products');
  await page.locator('select').first().selectOption({ label: 'Laptops' });
  await page.getByLabel('Search products', { exact: true }).fill('Laptop');
  await page.getByRole('button', { name: 'Apply', exact: true }).click();
  await expect(page.getByRole('link', { name: /^View .* details$/ }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Compare', exact: true }).nth(0).click();
  await page.getByRole('button', { name: 'Compare', exact: true }).nth(0).click();
  await page
    .getByRole('link', { name: /^View .* details$/ })
    .first()
    .click();
  await expect(
    page.getByRole('button', { name: 'Add to cart', exact: true }).first()
  ).toBeVisible();
  await page.getByRole('button', { name: 'Add to cart', exact: true }).first().click();
  await expect(page.getByRole('status')).toContainText('Added to cart.');
  await page.goto('/compare');
  await expect(page.getByRole('table')).toBeVisible();
  await page.goto('/cart');
  await expect(page.getByText(/Subtotal/).first()).toBeVisible();
  await page.goto('/checkout');
  await expect(
    page.getByRole('button', { name: 'Continue to secure checkout', exact: true })
  ).toBeVisible();
  await page.getByLabel('Recipient name', { exact: true }).fill('Local Test Shopper');
  await page.getByLabel('Phone', { exact: true }).fill('9999999999');
  await page.getByLabel('Address line 1', { exact: true }).fill('1 Fictional Test Street');
  await page.getByLabel('City', { exact: true }).fill('Hyderabad');
  await page.getByLabel('State or region', { exact: true }).fill('Telangana');
  await page.getByLabel('Postal code', { exact: true }).fill('500001');
  await expect(
    page.getByRole('button', { name: 'Continue to secure checkout', exact: true })
  ).toBeEnabled();
  await page.goto('/orders');
  await expect(page.getByRole('heading', { name: 'Order history', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true
  );
});
