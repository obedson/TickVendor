import { test, expect } from '@playwright/test';

test('organizer can open attendance check-in operations', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-organizer@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Check-in' }).click();
  await expect(page.getByRole('heading', { name: 'Attendance operations' })).toBeVisible();
  await page.getByLabel('QR token').fill('invalid');
  await page.getByRole('button', { name: 'Validate ticket' }).click();
  await expect(page.locator('body')).toContainText(/invalid|failed|not found|ticket|result/i);
});
