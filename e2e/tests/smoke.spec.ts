import { expect, test } from '@playwright/test';

// Walks the whole chain: browser -> nginx -> gunicorn/Django -> Postgres.
test('page loads through nginx and the backend reports healthy', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Job Management Dashboard' })).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('Backend: healthy');
});
