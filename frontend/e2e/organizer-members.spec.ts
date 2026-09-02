import { test, expect } from '@playwright/test';

test('organizer can open community members', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-organizer@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Community members' }).click();
  await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Private member' }).first()).toBeVisible();
});
