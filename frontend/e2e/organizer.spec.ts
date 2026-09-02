import { test, expect } from '@playwright/test';

test('organizer can open the real dashboard while participant has no organizer control', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-organizer@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('button', { name: 'Organizer dashboard' })).toBeVisible();
  await page.getByRole('button', { name: 'Organizer dashboard' }).click();
  await expect(page.getByRole('heading', { name: 'Organizer dashboard' })).toBeVisible();
  await expect(page.getByText('Upcoming events')).toBeVisible();
  await expect(page.getByText('Total events')).toBeVisible();
  await expect(page.getByText('Pending tasks')).toBeVisible();
});

test('participant does not receive organizer dashboard navigation', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-participant@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('button', { name: 'Organizer dashboard' })).not.toBeVisible();
});
