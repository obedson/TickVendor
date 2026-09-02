import { test, expect } from '@playwright/test';

test('real participant can acquire a free ticket and retain its QR wallet', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-participant@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'E2E Community Meetup' }).first()).toBeVisible();

  await page.getByRole('button', { name: 'View event' }).click();
  await expect(page.getByRole('heading', { name: 'Free admission' })).toBeVisible();
  await page.getByRole('button', { name: 'Acquire ticket' }).first().click();
  await expect(page.getByText('Ticket confirmed. Open My tickets to view it.')).toBeVisible();

  await page.getByRole('button', { name: 'My tickets' }).click();
  await expect(page.getByRole('heading', { name: 'E2E Community Meetup' }).first()).toBeVisible();
  await expect(page.getByAltText(/Entrance QR code/)).toBeVisible();
  await expect(page.getByText('Status: active')).toBeVisible();

  await page.reload();
  await page.getByRole('button', { name: 'My tickets' }).click();
  await expect(page.getByRole('heading', { name: 'E2E Community Meetup' }).first()).toBeVisible();
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

  const participantToken = await page.evaluate(() => {
    const session = JSON.parse(sessionStorage.getItem('tickvendor.session') || '{}');
    return session.access_token;
  });
  const assignmentsResponse = await page.request.get('http://127.0.0.1:8000/api/v1/task-assignments/me', {
    headers: { Authorization: `Bearer ${participantToken}` },
  });
  const assignment = (await assignmentsResponse.json())[0];
  const organizerLogin = await page.request.post('http://127.0.0.1:8000/api/v1/auth/login', {
    data: { email: 'e2e-organizer@example.com', password: 'e2e-password-123' },
  });
  const organizerSession = await organizerLogin.json();
  const verification = await page.request.post(
    `http://127.0.0.1:8000/api/v1/task-assignments/${assignment.id}/verify`,
    { headers: { Authorization: `Bearer ${organizerSession.access_token}` }, data: { approve: true } },
  );
  expect(verification.ok()).toBeTruthy();
  const verifiedAssignment = await page.request.get('http://127.0.0.1:8000/api/v1/task-assignments/me', {
    headers: { Authorization: `Bearer ${participantToken}` },
  });
  expect((await verifiedAssignment.json())[0].status).toBe('verified');

  await page.reload();
  await page.reload();
  await page.getByRole('button', { name: 'Tasks' }).click();
  await expect(page.getByText('Status: verified')).toBeVisible({ timeout: 10_000 });

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
  await page.getByRole('button', { name: 'Acquire ticket' }).first().click();
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

test('participant can load and submit peer confirmation', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('e2e-participant@example.com');
  await page.getByLabel('Password').fill('e2e-password-123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'View event' }).click();
  await page.getByRole('button', { name: 'Acquire ticket' }).first().click();
  await expect(page.getByText('Ticket confirmed. Open My tickets to view it.')).toBeVisible();
  await page.getByRole('button', { name: 'Attendance' }).click();
  await page.getByRole('button', { name: 'Check in' }).click();
  await expect(page.getByText(/Attendance status:/)).toBeVisible();
  await expect(page.getByText('No peer confirmations are currently available.')).not.toBeVisible({ timeout: 5_000 });
  await page.getByRole('button', { name: 'Confirm' }).click();
  await expect(page.getByText('Peer confirmation recorded.')).toBeVisible();
});
