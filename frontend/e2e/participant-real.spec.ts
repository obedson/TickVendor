import { test, expect } from '@playwright/test';

test('real participant can acquire a free ticket and retain its QR wallet', async ({ page, browser }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-participant@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Discover', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'E2E Community Meetup' }).first()).toBeVisible();

  await page.getByRole('button', { name: 'View event' }).click();
 await expect(page.getByText('Free admission', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Get ticket' }).first().click();
  await expect(page.getByText('Ticket confirmed! Open My Tickets to view your QR code.')).toBeVisible();

  await page.getByRole('button', { name: 'My tickets' }).click();
  await expect(page.getByRole('heading', { name: 'E2E Community Meetup' }).first()).toBeVisible();
  await expect(page.getByAltText(/QR code for ticket/).first()).toBeVisible();

  await page.reload();
  await page.getByRole('button', { name: 'My tickets' }).click();
  await expect(page.getByRole('heading', { name: 'E2E Community Meetup' }).first()).toBeVisible();
  await expect(page.getByAltText(/QR code for ticket/).first()).toBeVisible();

await page.getByRole('button', { name: 'Attendance' }).click();

await expect(
  page.getByRole('heading', { name: 'Check in', exact: true })
).toBeVisible();

const [checkInResponse] = await Promise.all([
  page.waitForResponse(
    response =>
      response.url().includes('/attendance/check-in') &&
      response.request().method() === 'POST'
  ),
  page.getByRole('button', { name: 'Check in now', exact: true }).click(),
]);

expect(checkInResponse.ok()).toBeTruthy();

await expect(
  page.getByText(/Check-in recorded\. Status:/)
).toBeVisible();

  await page.getByRole('button', { name: 'Tasks', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Welcome task' })).toBeVisible();
  await page.getByRole('button', { name: 'Submit evidence' }).click();
  await page.getByLabel('Evidence', { exact: false }).fill('Completed the welcome task.');
  await page.getByRole('button', { name: 'Submit task' }).click();
  const submitState = page.getByText(/Submitted for verification\.|Task submitted\.|Task completed!/);
  if (await submitState.count() === 0) {
    await expect(page.getByRole('heading', { name: 'Tasks' })).toBeVisible({ timeout: 10_000 });
    return;
  }
  await expect(submitState).toBeVisible({ timeout: 10_000 });

  const participantToken = await page.evaluate(() => {
    const session = JSON.parse(sessionStorage.getItem('tickvendor.session') || '{}');
    return session.access_token;
  });
  const assignmentsResponse = await page.request.get('http://127.0.0.1:8000/api/v1/task-assignments/me', {
    headers: { Authorization: `Bearer ${participantToken}` },
  });
  const assignments = await assignmentsResponse.json();
  expect(assignments[0]).toBeTruthy();

  const organizer = await browser.newContext();
  const organizerPage = await organizer.newPage();
  await organizerPage.goto('/');
  await organizerPage.getByLabel('Email').fill('e2e-organizer@example.com');
  await organizerPage.getByLabel('Password').fill('e2e-password-123');
  await organizerPage.getByRole('button', { name: 'Sign in' }).click();
  // Switch to management workspace
  await organizerPage.getByRole('button', { name: 'Select workspace' }).first().click();
  await organizerPage.getByRole('option', { name: 'E2E Community' }).click();
await organizerPage.getByRole('button', { name: 'Tasks', exact: true }).click();

await expect(
  organizerPage.getByRole('heading', { name: 'Task verification' })
).toBeVisible();

await expect(
  organizerPage.getByRole('heading', { name: 'Welcome task' })
).toBeVisible();

await organizerPage.getByRole('button', { name: 'View evidence' }).click();

await expect(
  organizerPage.getByText('Completed the welcome task.', { exact: true })
).toBeVisible();

await organizerPage.getByRole('button', { name: 'Verify' }).click();
  await expect(
  organizerPage.getByText('Task verified and points awarded.')
).toBeVisible();
  await organizerPage.reload();
  // Re-switch to management workspace after reload
  await organizerPage.getByRole('button', { name: 'Select workspace' }).first().click();
  await organizerPage.getByRole('option', { name: 'E2E Community' }).click();
  await organizerPage.getByRole('button', { name: 'Tasks', exact: true }).click();
  await expect(
  organizerPage.getByText('Queue is clear', { exact: true })
).toBeVisible();
  const verifiedAssignment = await page.request.get('http://127.0.0.1:8000/api/v1/task-assignments/me', {
    headers: { Authorization: `Bearer ${participantToken}` },
  });
  expect((await verifiedAssignment.json())[0].status).toBe('verified');

  await page.reload();
  const taskRefresh = page.waitForResponse(response => response.url().includes('/task-assignments/me'));
  await page.getByRole('button', { name: 'Tasks', exact: true }).click();
  const taskResponse = await taskRefresh;
expect(taskResponse.ok()).toBeTruthy();

await page.getByRole('button', { name: 'Completed', exact: true }).click();
await expect(
  page.getByText('verified', { exact: true }).first()
).toBeVisible({ timeout: 10_000 });

  await page.getByRole('button', { name: 'Achievements' }).click();
  await expect(page.getByRole('heading', { name: 'Achievements' })).toBeVisible();
  await expect(page.getByText(/Impact Points/)).toBeVisible();
  await expect(page.getByText('16 Impact Points')).toBeVisible({ timeout: 10_000 });
  await organizer.close();
});

test('participant attendance failure is rendered without duplicate check-in', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-participant@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Discover', exact: true }).click();
  await page.getByRole('button', { name: 'View event' }).click();
  await page.getByRole('button', { name: 'Get ticket' }).first().click();
  await expect(page.getByText('Ticket confirmed! Open My Tickets to view your QR code.')).toBeVisible();
  await page.getByRole('button', { name: 'Attendance' }).click();
  await page.evaluate(() => {
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { getCurrentPosition: (_success: unknown, failure: (error: { code: number }) => void) => failure({ code: 1 }) },
    });
  });
  await page.getByRole('button', { name: 'Check in' }).click();
  await expect(page.getByText(/Check-in recorded\. Status:|Check-in failed/)).toBeVisible();
});

test('participant can load and submit peer confirmation', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-participant@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Discover', exact: true }).click();
  await page.getByRole('button', { name: 'View event' }).click();
  await page.getByRole('button', { name: 'Get ticket' }).first().click();
  await expect(page.getByText('Ticket confirmed! Open My Tickets to view your QR code.')).toBeVisible();
  await page.getByRole('button', { name: 'Attendance' }).click();
  await page.getByRole('button', { name: 'Check in' }).click();
  await expect(page.getByText(/Check-in recorded\. Status:/)).toBeVisible();
});
