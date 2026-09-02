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

  await page.getByRole('button', { name: 'Attendance' }).click();
  await expect(page.getByRole('heading', { name: 'Attendance' })).toBeVisible();
  await page.getByRole('button', { name: 'Check in' }).click();
  await page.waitForResponse(response => response.url().includes('/attendance/check-in'));
  await expect(page.getByText(/Attendance status:/)).toBeVisible();

  await page.getByRole('button', { name: 'Tasks' }).click();
  await expect(page.getByRole('heading', { name: 'Welcome task' })).toBeVisible();
  await page.getByRole('button', { name: 'Submit evidence' }).click();
  await page.getByLabel('Evidence').fill('Completed the welcome task.');
  await page.getByRole('button', { name: 'Submit task' }).click();
  await expect(page.getByText('Submitted for verification.')).toBeVisible();

  await page.getByRole('button', { name: 'Impact' }).click();
  await expect(page.getByRole('heading', { name: 'Recognition' })).toBeVisible();
  await expect(page.getByText(/Impact Points/)).toBeVisible();
});

test('participant attendance failure is rendered without duplicate check-in', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-participant@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'View event' }).click();
  await page.getByRole('button', { name: 'Acquire ticket' }).click();
  await expect(page.getByText('Ticket confirmed. Open My tickets to view it.')).toBeVisible();
  await page.getByRole('button', { name: 'Attendance' }).click();
  await page.evaluate(() => {
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: (_success: unknown, failure: (error: { code: number }) => void) => failure({ code: 1 }) },
    });
  });
  await page.getByRole('button', { name: 'Check in' }).click();
  await expect(page.getByText(/Attendance status:|Check-in failed/)).toBeVisible();
});
