import { test, expect } from '@playwright/test';

test('participant auth and navigation shell reaches core views', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('tickvendor.session', JSON.stringify({
      access_token: 'e2e-access-token', refresh_token: 'e2e-refresh-token',
      user: { id: 'participant', email: 'participant@example.com', role: 'participant', username: 'participant', display_name: 'Participant' },
    }));
  });
  await page.route('**/api/v1/auth/me', async route => route.fulfill({ json: { id: 'participant' } }));
  await page.route('**/api/v1/events?search=', async route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/tickets/me', async route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/profiles/me', async route => route.fulfill({ json: { display_name: 'Participant', impact_points: 0, rank: null, next_rank: null, badges: [], milestones: [], events_attended: 0, tasks_completed: 0 } }));
  await page.route('**/api/v1/task-assignments/me/details', async route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/communities/me', async route => route.fulfill({ json: [] }));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Tasks', exact: true })).toBeVisible();
await page.getByRole('button', { name: 'Tasks', exact: true }).click();
await expect(page.getByRole('heading', { name: 'Tasks', exact: true })).toBeVisible();

await page.getByRole('button', { name: 'Achievements', exact: true }).click();
await expect(page.getByRole('heading', { name: 'Achievements' })).toBeVisible();

await page.getByRole('button', { name: 'Communities', exact: true }).click();
await expect(page.getByRole('heading', { name: 'Your communities' })).toBeVisible();
});

test('payment return uses backend status and never provider success query', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('tickvendor.session', JSON.stringify({
      access_token: 'e2e-access-token', refresh_token: 'e2e-refresh-token',
      user: { id: 'participant', email: 'participant@example.com', role: 'participant', username: 'participant', display_name: 'Participant' },
    }));
  });
  let statusCalls = 0;
  await page.route('**/api/v1/auth/me', async route => route.fulfill({ json: { id: 'participant' } }));
  await page.route('**/api/v1/payments/payment-1', async route => {
    statusCalls += 1;
    await route.fulfill({ json: { status: statusCalls === 1 ? 'pending' : 'successful', order_reference: 'ORDER-1' } });
  });
  await page.goto('/?payment_id=payment-1&status=success');
  await expect(page.getByText('Payment processing')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Payment confirmed!' })).toBeVisible({ timeout: 8_000 });
  expect(statusCalls).toBe(2);
  await expect(page.getByText(/Your ticket has been issued and is available in My Tickets\./)).toBeVisible();
});
