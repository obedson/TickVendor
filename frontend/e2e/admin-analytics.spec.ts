import { test, expect } from '@playwright/test';

test('community administrator can view authoritative analytics', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-admin@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  // Switch to management workspace to access admin navigation
  await page.getByRole('button', { name: 'Select workspace' }).first().click();
  await page.getByRole('option', { name: 'E2E Community' }).click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Analytics', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Community analytics' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Total members', exact: true })).toBeVisible();
  await expect(page.getByText('Impact Points awarded', { exact: true })).toBeVisible();
});
