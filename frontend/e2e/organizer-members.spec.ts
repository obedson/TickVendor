import { test, expect } from '@playwright/test';

test('organizer can open community members', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-organizer@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  // Switch to management workspace to access organizer navigation
  await page.getByRole('button', { name: 'Select workspace' }).first().click();
  await page.getByRole('option', { name: 'E2E Community' }).click();
  await page.getByRole('button', { name: 'Members' }).click();
  await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible();
  await expect(page.getByText('Private member', { exact: true }).first()).toBeVisible();
});
