import { expect, test } from '@playwright/test';

import { createJob, jobRow, statusCell, uniqueJobName } from './helpers';

// Each test walks the whole chain: browser -> nginx -> gunicorn/Django -> Postgres.
// Neither assumes an empty table or a test order: each creates its own job
// under a unique name and only ever looks at that job's row.

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Job Management Dashboard' })).toBeVisible();
});

// A new job is listed as Pending; a status change shows in its row and is
// what the server stored, not only what the page remembers.
test('a created job is listed as Pending and keeps a changed status after a reload', async ({ page }) => {
  const name = uniqueJobName('status');

  const row = await createJob(page, name);
  await expect(statusCell(row, 'Pending')).toBeVisible();

  await page.getByRole('button', { name: `Change status of ${name}` }).click();
  await page.getByRole('menuitem', { name: 'Running' }).click();
  // The row changes only once the PATCH has succeeded and the list has been
  // fetched again, so after this line the reload cannot cut the request off.
  await expect(statusCell(row, 'Running')).toBeVisible();

  await page.reload();
  await expect(statusCell(jobRow(page, name), 'Running')).toBeVisible();
});

// A deleted job leaves the list. The row was on screen first (`createJob`
// waits for it), so "no such row" cannot pass on a page that has not loaded.
test('a deleted job is removed from the list', async ({ page }) => {
  const name = uniqueJobName('delete');

  await createJob(page, name);

  await page.getByRole('button', { name: `Delete ${name}` }).click();
  // The confirmation's own button; the row's bin button is named "Delete <name>".
  await page.getByRole('button', { name: 'Delete', exact: true }).click();

  await expect(jobRow(page, name)).toHaveCount(0);
});
