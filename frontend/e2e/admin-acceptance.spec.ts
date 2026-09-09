import { test, expect } from '@playwright/test';

test('administrator can adjust participant points and find audit trace', async ({ browser }) => {
  const participant = await browser.newPage();

  await participant.goto('/');
  await participant.getByLabel('Email').fill('e2e-peer@example.com');
  await participant.getByLabel('Password').fill('e2e-password-123');
  await participant.getByRole('button', { name: 'Sign in' }).click();

  await participant.getByRole('button', { name: 'Achievements' }).click();
  await expect(
    participant.getByRole('heading', { name: 'Achievements', exact: true })
  ).toBeVisible();

  const impactPoints = participant.getByText('Total Impact Points', { exact: true }).locator('..');
  const beforeText = await impactPoints.innerText();
  const before = Number(beforeText.match(/\d+/)?.[0]);

  const participantToken = await participant.evaluate(
    () => JSON.parse(sessionStorage.getItem('tickvendor.session') || '{}').access_token
  );

  const participantId = await (
    await participant.request.get('http://127.0.0.1:8000/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${participantToken}` },
    })
  ).json().then(user => user.id);

  const admin = await browser.newPage();

  await admin.goto('/');
  await admin.getByLabel('Email').fill('e2e-admin@example.com');
  await admin.getByLabel('Password').fill('e2e-password-123');
  await admin.getByRole('button', { name: 'Sign in' }).click();

  await admin.getByRole('button', { name: 'Select workspace' }).first().click();
  await admin.getByRole('option', { name: 'E2E Community' }).click();

  await admin.getByRole('button', { name: 'Impact', exact: true }).click();
  await admin.getByRole('button', { name: 'Adjustments', exact: true }).click();

  await expect(
    admin.getByRole('heading', { name: 'Manual Impact Point adjustment' })
  ).toBeVisible();

  await expect(
    admin.getByLabel('Participant').locator('option').nth(1)
  ).toHaveCount(1, { timeout: 10_000 });

  await admin.getByLabel('Participant').selectOption(participantId);
  await admin.getByLabel('Amount').fill('7');
  await admin.getByLabel('Reason').fill('Acceptance adjustment');
  await admin.getByRole('button', { name: 'Adjust points' }).click();

  const status = admin.getByRole('status').filter({
    hasText: /adjusted.*reference/i,
  });

  await expect(status).toBeVisible();

  const result = await status.innerText();
  const reference = result.match(/Reference ([0-9a-f-]+)/i)?.[1];

  expect(reference).toBeTruthy();

  await participant.reload();
  await participant.getByRole('button', { name: 'Achievements' }).click();

  const updatedImpactPoints = participant
    .getByText('Total Impact Points', { exact: true })
    .locator('..');

  const afterText = await updatedImpactPoints.innerText();
  const after = Number(afterText.match(/\d+/)?.[0]);

  expect(after).toBe(before + 7);

  await admin.getByRole('button', { name: 'Settings', exact: true }).click();
  await admin.getByRole('button', { name: 'Audit log', exact: true }).click();

  await admin.getByLabel('Action filter').fill('impact.adjusted');

  await expect(
    admin.getByText('impact.adjusted').first()
  ).toBeVisible();

 await admin.getByRole('button', { name: 'Details', exact: true }).first().click();

await expect(
  admin.getByText(reference!, { exact: false })
).toBeVisible();

  await admin.close();
  await participant.close();
});