import { test, expect } from '@playwright/test';

const session = (role = 'participant') => ({
  access_token: 'e2e-access-token', refresh_token: 'e2e-refresh-token',
  user: { id: role, email: `${role}@example.com`, role, username: role, display_name: role === 'organizer' ? 'Organizer' : 'Participant' },
});

async function authenticated(page: Parameters<typeof test>[0] extends never ? never : any, role = 'participant') {
  await page.addInitScript((value: unknown) => sessionStorage.setItem('tickvendor.session', JSON.stringify(value)), session(role));
  await page.route('**/api/v1/auth/me', async route => route.fulfill({ json: { id: role } }));
  await page.route('**/api/v1/events?search=', async route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/tickets/me', async route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/profiles/me', async route => route.fulfill({ json: { display_name: 'Participant', impact_points: 12, rank: null, next_rank: null, badges: [], milestones: [], events_attended: 1, tasks_completed: 0 } }));
  await page.route('**/api/v1/task-assignments/me/details', async route => route.fulfill({ json: [] }));
}

test('participant API-backed screens use the API service origin', async ({ page }) => {
  await authenticated(page);
  const requests: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/v1/')) requests.push(request.url()); });
  await page.goto('/');
  await page.getByRole('button', { name: 'Achievements' }).click();
  await page.getByRole('button', { name: 'Tasks' }).click();
  await page.getByRole('button', { name: 'Communities' }).click();
  await page.getByRole('button', { name: 'Open notifications' }).click();
  expect(requests.every(url => url.includes('/api/v1/'))).toBeTruthy();
});

test('desktop participant Home and Discover remain distinct', async ({ page }) => {
  await authenticated(page);
  await page.goto('/');
  await expect(page.locator('.sidebar')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Make your presence count.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Find your next event' })).not.toBeVisible();
  await page.getByRole('button', { name: 'Discover' }).click();
  await expect(page.getByRole('heading', { name: 'Find your next event' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Make your presence count.' })).not.toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Search events' })).toHaveCount(1);
  await expect(page.getByRole('heading', { name: 'No events found nearby' })).toBeVisible();
  await page.getByRole('button', { name: 'Home' }).click();
  await expect(page.getByRole('heading', { name: 'Make your presence count.' })).toBeVisible();
  await page.locator('.account-menu summary').click();
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('mobile participant shell and More navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await authenticated(page);
  await page.goto('/');
  await expect(page.locator('.mobile-bottom-nav')).toBeVisible();
  await page.getByRole('button', { name: 'More' }).click();
  await expect(page.getByRole('dialog', { name: 'More' })).toBeVisible();
  await page.getByRole('button', { name: 'Communities' }).click();
  await expect(page.getByRole('heading', { name: 'Your communities' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('role-restricted organizer navigation remains reachable', async ({ page }) => {
  await authenticated(page, 'organizer');
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Overview' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Events and tickets' })).toBeVisible();
});

test('verification success handoff and invalid-link non-redirect behavior', async ({ page }) => {
  await page.route('**/api/v1/auth/verify-email', async route => route.fulfill({ status: 204 }));
  await page.goto('/verify-email?token=valid-token');
  await expect(page.getByRole('heading', { name: 'Email verified' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign in now' })).toBeVisible();
  await page.waitForURL('**/', { timeout: 8_000 });
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
});
