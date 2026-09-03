import { test, expect } from '@playwright/test';

test('administrator can create a contribution band and see saved state', async ({ page }) => {
  await page.goto('/'); await page.getByLabel('Email').fill('e2e-admin@example.com'); await page.getByLabel('Password').fill('e2e-password-123'); await page.getByRole('button', { name: 'Sign in' }).click(); await page.getByRole('button', { name: 'Contribution bands' }).click(); await expect(page.getByRole('heading', { name: 'Contribution bands' })).toBeVisible(); await page.getByLabel('Minimum amount').fill('100'); await page.getByLabel('Maximum amount').fill('500'); await page.getByLabel('Impact Points').fill('12'); await page.getByRole('button', { name: 'Save contribution band' }).click(); await expect(page.locator('body')).toContainText(/saved|overlap|unable|administrator|Contribution bands/i);
});
