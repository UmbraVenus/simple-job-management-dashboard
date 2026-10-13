import { randomUUID } from 'node:crypto';

import { expect } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

/**
 * A job name no other test, retry or earlier run has used.
 *
 * Job names are unique in the app, and a retried test runs against the same
 * database as its first attempt: a fixed name would make the retry fail with
 * "A job with this name already exists" whatever the first failure was.
 *
 * The random part has a fixed length and comes last, so one name is never the
 * start of another (`jobRow` matches by substring).
 */
export function uniqueJobName(label: string): string {
  return `E2E ${label} ${randomUUID().slice(0, 8)}`;
}

/** The table row of one job. Every check on a job goes through its row, never the whole page. */
export function jobRow(page: Page, name: string): Locator {
  return page.getByRole('row', { name });
}

/** The status cell of a row, matched on the label the user reads (e.g. "Pending"). */
export function statusCell(row: Locator, label: string): Locator {
  return row.getByRole('cell', { name: label, exact: true });
}

/**
 * Create a job through the form and wait until the list shows it.
 *
 * @returns The new job's row.
 */
export async function createJob(page: Page, name: string): Promise<Locator> {
  await page.getByLabel('Job name').fill(name);
  await page.getByRole('button', { name: 'Create job' }).click();

  const row = jobRow(page, name);
  await expect(row).toBeVisible();
  return row;
}
