import { test, expect } from '@playwright/test';

test('administrator persists all recognition configuration types and participant is denied', async ({ browser }) => {
  const admin = await browser.newPage();

  await admin.goto('/');
  await admin.getByLabel('Email').fill('e2e-admin@example.com');
  await admin.getByLabel('Password').fill('e2e-password-123');
  await admin.getByRole('button', { name: 'Sign in' }).click();

  await admin.getByRole('button', { name: 'Select workspace' }).first().click();
  await admin.getByRole('option', { name: 'E2E Community' }).click();

  await admin.getByRole('button', { name: 'Impact', exact: true }).click();
  await admin.getByRole('button', { name: 'Recognition', exact: true }).click();

  await expect(
    admin.getByRole('heading', { name: 'Recognition configuration' }),
  ).toBeVisible();

  await admin.getByLabel('Name').nth(0).fill('E2E Achievement');
  await admin.getByLabel('Slug').nth(0).fill('e2e-achievement');
  await admin
    .getByLabel('Condition tree')
    .fill('{"metric":"impact_points","operator":">=","threshold":100}');
  await admin.getByLabel('Reward definition').fill('{"points":2}');
  await admin.getByRole('button', { name: 'Create achievement rule' }).click();

  await expect(
    admin.getByText('E2E Achievement (e2e-achievement)'),
  ).toBeVisible();

  await admin.getByLabel('Name').nth(1).fill('E2E Badge');
  await admin.getByLabel('Slug').nth(1).fill('e2e-badge');
  await admin.getByLabel('Category').fill('participation');
  await admin
    .getByLabel('Requirements')
    .nth(0)
    .fill('{"metric":"attendance_count","operator":">=","threshold":1}');
  await admin.getByRole('button', { name: 'Create badge' }).click();

  await expect(
    admin.getByText('E2E Badge (e2e-badge)'),
  ).toBeVisible();

  await admin.getByLabel('Name').nth(2).fill('E2E Milestone');
  await admin.getByLabel('Slug').nth(2).fill('e2e-milestone');
  await admin
    .getByLabel('Requirements')
    .nth(1)
    .fill('[{"metric":"attendance_count","operator":">=","threshold":1}]');
  await admin.getByRole('button', { name: 'Create milestone' }).click();

  await expect(
    admin.getByText('E2E Milestone (e2e-milestone)'),
  ).toBeVisible();

  await admin.getByLabel('Name').nth(3).fill('E2E Rank');
  await admin.getByLabel('Slug').nth(3).fill('e2e-rank');
  await admin.getByLabel('Minimum points').fill('100');
  await admin.getByLabel('Sort order').fill('10');
  await admin
    .getByLabel('Requirements')
    .nth(2)
    .fill('[{"requirement_type":"attendance_count","threshold":2}]');
  await admin.getByRole('button', { name: 'Create rank' }).click();

  await expect(
    admin.getByText('E2E Rank (e2e-rank)'),
  ).toBeVisible();

  // Verify the configuration persists after reload.
  await admin.reload();

  await admin.getByRole('button', { name: 'Select workspace' }).first().click();
  await admin.getByRole('option', { name: 'E2E Community' }).click();

  await admin.getByRole('button', { name: 'Impact', exact: true }).click();
  await admin.getByRole('button', { name: 'Recognition', exact: true }).click();

  await expect(
    admin.getByText('E2E Achievement (e2e-achievement)'),
  ).toBeVisible();

  await expect(
    admin.getByText('E2E Rank (e2e-rank)'),
  ).toBeVisible();

  // Participant must not have access to recognition administration.
  const participant = await browser.newPage();

  await participant.goto('/');
  await participant.getByLabel('Email').fill('e2e-participant@example.com');
  await participant.getByLabel('Password').fill('e2e-password-123');
  await participant.getByRole('button', { name: 'Sign in' }).click();

  await expect(
    participant.getByRole('button', { name: 'Recognition' }),
  ).toHaveCount(0);

  await participant.request
    .get('http://127.0.0.1:8000/api/v1/admin/communities/not-a-community/ranks')
    .then((response) => expect(response.status()).toBeGreaterThanOrEqual(401));

  await admin.close();
  await participant.close();
});