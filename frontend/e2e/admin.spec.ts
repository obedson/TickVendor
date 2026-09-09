import { test, expect } from '@playwright/test';

test('administrator can open point rules and audit log without exposing them to participants', async ({ browser }) => {
  const admin = await browser.newPage();
  await admin.goto('/');
  await admin.getByLabel('Email').fill('e2e-admin@example.com');
  await admin.getByLabel('Password').fill('e2e-password-123');
  await admin.getByRole('button', { name: 'Sign in' }).click();
  // Switch to management workspace to access admin navigation
  await admin.getByRole('button', { name: 'Select workspace' }).first().click();
  await admin.getByRole('option', { name: 'E2E Community' }).click();
  await admin.getByRole('button', { name: 'Settings', exact: true }).click();
await expect(admin.getByRole('button', { name: 'Point rules', exact: true })).toBeVisible();
await admin.getByRole('button', { name: 'Point rules', exact: true }).click();
  await expect(admin.getByRole('heading', { name: 'Point rules' })).toBeVisible();
  await admin.getByRole('button', { name: 'Audit log' }).click();
  await expect(admin.getByRole('heading', { name: 'Audit log' })).toBeVisible();
  const participant = await browser.newPage();
  await participant.goto('/');
  await participant.getByLabel('Email').fill('e2e-participant@example.com');
  await participant.getByLabel('Password').fill('e2e-password-123');
  await participant.getByRole('button', { name: 'Sign in' }).click();
  await expect(participant.getByRole('button', { name: 'Point rules' })).toHaveCount(0);
  await expect(participant.getByRole('button', { name: 'Audit log' })).toHaveCount(0);
  await admin.close(); await participant.close();
});
