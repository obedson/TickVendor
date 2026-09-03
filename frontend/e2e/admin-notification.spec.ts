import { test, expect } from '@playwright/test';

test('administrator can persist a community notification rule', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-admin@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Notification rules' }).click();
  await expect(page.getByRole('heading', { name: 'Notification rules' })).toBeVisible();
  await page.getByLabel('Notification type').fill('task_verified');
  await page.getByLabel('Email enabled').check();
  await page.getByRole('button', { name: 'Save notification rule' }).click();
  await expect(page.getByRole('status')).toContainText('saved');
  await expect(page.getByText('task_verified · Active · Email · No push')).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Notification rules' }).click();
  await expect(page.getByText('task_verified · Active · Email · No push')).toBeVisible();
});
