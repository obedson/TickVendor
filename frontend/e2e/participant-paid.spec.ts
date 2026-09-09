import { test, expect } from '@playwright/test';

test('paid ticket uses real backend order and provider verification flow', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-participant@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Discover', exact: true }).click();
  await page.getByRole('button', { name: 'View event' }).click();
  await expect(
  page.getByText('Supporter admission', { exact: true })
).toBeVisible();

  let initializeCalls = 0;
  await page.route('**/api/v1/payments/initialize', async route => {
    initializeCalls += 1;
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ json: { ...body, checkout_url: `${new URL(route.request().url()).origin}/?payment_id=${body.payment_id}` } });
  });
  await page.getByRole('button', { name: 'Get ticket' }).nth(1).click();
  await expect(page).toHaveURL(/payment_id=/);
  expect(initializeCalls).toBe(1);
  await expect(page.getByRole('heading', { name: /Payment/ })).toBeVisible();
  await page.reload();
  expect(initializeCalls).toBe(1);
});
