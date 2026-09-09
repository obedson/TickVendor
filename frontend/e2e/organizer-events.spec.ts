import { test, expect } from '@playwright/test';

async function switchToManagement(page: any) {
  await page.getByRole('button', { name: 'Select workspace' }).first().click();
  await page.getByRole('option', { name: 'E2E Community' }).click();
}

test('organizer can open the real event-management list', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-organizer@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await switchToManagement(page);
  await page.getByRole('button', { name: 'Events' }).click();
  await expect(page.getByRole('heading', { name: 'Events' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'E2E Community Meetup' })).toBeVisible();
  await expect(page.getByText('published', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '+ Create event', exact: true }).click();

  await page.getByLabel('Title').fill('Organizer-created event');
  await page.getByLabel('Description').fill('A real event created through the organizer interface.');
  await page.getByLabel('Start').fill('2026-12-10T10:00');
  await page.getByLabel('End').fill('2026-12-10T12:00');
  await page.getByLabel('Venue name').fill('E2E Community Centre');
  await page.getByLabel('Venue address').fill('123 Test Street');
  await page.getByLabel('City').fill('Enugu');
  await page.getByLabel('State / Region').fill('Enugu');

  await page.getByRole('button', { name: 'Create event' }).click();
 await expect(
  page.getByText('Event "Organizer-created event" created.', { exact: true })
).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Organizer-created event' })).toBeVisible();
});

test('organizer can open attendance configuration for an owned event', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-organizer@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await switchToManagement(page);
  await page.getByRole('button', { name: 'Events' }).click();
  await page.getByRole('button', { name: 'Configure', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Attendance configuration' })).toBeVisible();
  await page.getByRole('button', { name: 'Save attendance settings' }).click();
  await expect(page.getByText('Attendance configuration saved.')).toBeVisible();
});
