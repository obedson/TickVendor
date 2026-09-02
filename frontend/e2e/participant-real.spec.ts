import { test, expect } from '@playwright/test';

test('real participant can acquire a free ticket and retain its QR wallet', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-participant@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'E2E Community Meetup' })).toBeVisible();

  await page.getByRole('button', { name: 'View event' }).click();
  await expect(page.getByRole('heading', { name: 'Free admission' })).toBeVisible();
  await page.getByRole('button', { name: 'Acquire ticket' }).click();
  await expect(page.getByText('Ticket confirmed. Open My tickets to view it.')).toBeVisible();

  await page.getByRole('button', { name: 'My tickets' }).click();
  await expect(page.getByRole('heading', { name: 'E2E Community Meetup' })).toBeVisible();
  await expect(page.getByAltText(/Entrance QR code/)).toBeVisible();
  await expect(page.getByText('Status: active')).toBeVisible();

  await page.reload();
  await page.getByRole('button', { name: 'My tickets' }).click();
  await expect(page.getByRole('heading', { name: 'E2E Community Meetup' })).toBeVisible();
  await expect(page.getByAltText(/Entrance QR code/)).toBeVisible();
});
