import { test, expect } from '@playwright/test';

test('successful verification offers sign-in and redirects to the auth route', async ({ page }) => {
  await page.route('**/api/v1/auth/verify-email', async route =>
    route.fulfill({ status: 204 })
  );

  await page.goto('/verify-email?token=test-verification-token');
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign in now' })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Redirecting to sign in');
  await page.waitForURL('**/');
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
});

test('invalid verification does not redirect', async ({ page }) => {
  await page.route('**/api/v1/auth/verify-email', async route =>
    route.fulfill({ status: 400, json: { detail: 'Invalid or expired verification token' } })
  );

  await page.goto('/verify-email?token=invalid-token');
  await expect(page.getByRole('heading', { name: 'Verification link unavailable' })).toBeVisible();
  await page.waitForTimeout(4500);
  expect(new URL(page.url()).pathname).toBe('/verify-email');
});
