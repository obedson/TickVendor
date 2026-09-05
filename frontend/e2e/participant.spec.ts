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
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Tasks' })).toBeVisible();
  await page.getByRole('button', { name: 'Tasks' }).click();
  await expect(page.getByRole('heading', { name: 'Tasks' })).toBeVisible();
  await page.getByRole('button', { name: 'Achievements' }).click();
  await expect(page.getByRole('heading', { name: 'Achievements' })).toBeVisible();
  await page.getByRole('button', { name: 'Communities' }).click();
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
  await expect(page.getByText('Payment pending')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Payment verified' })).toBeVisible({ timeout: 8_000 });
  expect(statusCalls).toBe(2);
  await expect(page.getByText('Your ticket is now available in My Tickets.')).toBeVisible();
});
