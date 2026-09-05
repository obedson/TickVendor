import { test, expect } from '@playwright/test';

test('organizer can open attendance review queue', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-organizer@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Attendance review' }).click();
  await expect(page.getByRole('heading', { name: 'Attendance review' })).toBeVisible();
  await expect(page.getByText(/No flagged attendance needs review\.|No review items/)).toBeVisible();
});
