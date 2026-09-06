import { test, expect } from '@playwright/test';

test('participant discovers and joins a community opportunity', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-participant@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Opportunities' }).click();
  await expect(page.getByRole('heading', { name: 'Community opportunities' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'E2E Park Cleanup' })).toBeVisible();
  await page.getByRole('button', { name: 'View opportunity' }).click();
  await expect(page.getByRole('heading', { name: 'E2E Park Cleanup' })).toBeVisible();
  await page.getByRole('button', { name: 'Join opportunity' }).click();
  await expect(page.getByRole('status')).toContainText('registered');
});
