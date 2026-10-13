import { expect, test } from '@playwright/test';

// Walks the whole chain: browser -> nginx -> gunicorn/Django -> Postgres.
// The empty state is shown only after the list request has succeeded, and
// every run starts from an empty database.
// TODO: the create / change status / delete flows are Phase 7 (jobs.spec.ts).
test('page loads through nginx and lists the jobs from the backend', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Job Management Dashboard' })).toBeVisible();
  await expect(page.getByText('No jobs yet')).toBeVisible();
  await expect(page.getByLabel('Job name')).toBeEditable();
});
