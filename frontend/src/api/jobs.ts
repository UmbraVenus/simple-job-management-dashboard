import type { Job, JobStatusType, Page } from '../types/job';
import { request } from './client';
import { decodeJob, decodeJobPage } from './decode';

// Every URL ends with a slash: without it Django answers 301, and a browser
// replays a redirected PATCH or DELETE as a GET.
const JOBS_URL = '/api/jobs/';

/** Jobs per page. Fixed by the server (jobs/pagination.py); the client cannot ask for more. */
export const PAGE_SIZE = 20;

function jobUrl(id: number): string {
  return `${JOBS_URL}${id}/`;
}

/**
 * Fetch one page of jobs, newest first.
 *
 * @param cursor Position from a previous page's `next` / `previous`, or `null` for the first page.
 * @param signal Cancels the request when the page is no longer wanted.
 */
export async function listJobs(cursor: string | null, signal?: AbortSignal): Promise<Page<Job>> {
  const url = cursor === null ? JOBS_URL : `${JOBS_URL}?${new URLSearchParams({ cursor }).toString()}`;
  return decodeJobPage(await request(url, signal === undefined ? {} : { signal }));
}

/** Create a job; the server starts it as `PENDING`. */
export async function createJob(name: string): Promise<Job> {
  return decodeJob(await request(JOBS_URL, { method: 'POST', body: { name } }));
}

/** Set a job's status. Every call appends an entry to the job's status log. */
export async function updateJobStatus(id: number, status: JobStatusType): Promise<Job> {
  return decodeJob(await request(jobUrl(id), { method: 'PATCH', body: { status_type: status } }));
}

/** Delete a job and its status log. */
export async function deleteJob(id: number): Promise<void> {
  await request(jobUrl(id), { method: 'DELETE' });
}
