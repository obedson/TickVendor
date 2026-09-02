import { test, expect } from '@playwright/test';

test('organizer verifies submitted task evidence through the browser', async ({ browser }) => {
  const participant = await browser.newContext();
  const participantPage = await participant.newPage();
  await participantPage.goto('/');
  await participantPage.getByLabel('Email').fill('e2e-participant@example.com');
  await participantPage.getByLabel('Password').fill('e2e-password-123');
  await participantPage.getByRole('button', { name: 'Sign in' }).click();
  await participantPage.getByRole('button', { name: 'Tasks' }).click();
  await participantPage.getByRole('button', { name: 'Submit evidence' }).click();
  await participantPage.getByLabel('Evidence').fill('Browser-reviewed evidence.');
  await participantPage.getByRole('button', { name: 'Submit task' }).click();
  await expect(participantPage.getByText('Submitted for verification.')).toBeVisible();

  const organizer = await browser.newContext();
  const organizerPage = await organizer.newPage();
  await organizerPage.goto('/');
  await organizerPage.getByLabel('Email').fill('e2e-organizer@example.com');
  await organizerPage.getByLabel('Password').fill('e2e-password-123');
  await organizerPage.getByRole('button', { name: 'Sign in' }).click();
  await organizerPage.getByRole('button', { name: 'Review tasks' }).click();
  await expect(organizerPage.getByRole('heading', { name: 'Task verification' })).toBeVisible();
  await expect(organizerPage.getByText('Browser-reviewed evidence.')).toBeVisible();
  await organizerPage.getByRole('button', { name: 'Verify' }).click();
  await expect(organizerPage.getByText('Task verified.')).toBeVisible();
  await expect(organizerPage.getByText('No task submissions need review.')).toBeVisible();
  await participant.close();
  await organizer.close();
});
