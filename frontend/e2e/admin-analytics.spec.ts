import { test, expect } from '@playwright/test';

test('community administrator can view authoritative analytics', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-admin@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Analytics' }).click();
  await expect(page.getByRole('heading', { name: 'Community analytics' })).toBeVisible();
  await expect(page.getByText('Members')).toBeVisible();
  await expect(page.getByText('Impact Points')).toBeVisible();
});
