import { isJobStatusType } from '../types/job';
import type { Job, Page } from '../types/job';
import { ApiError, isRecord } from './client';

// TODO: no frontend unit tests. Deferred: the chosen stretch goal is backend
//  unit tests; the UI is covered by the Playwright flows. Fix: Vitest, starting
//  with the pure modules (this file, features/jobs/relativeTime.ts).

// Response bodies arrive as `unknown`. These functions check the shape at run
// time, so a body the types do not describe fails here, as an ApiError the UI
// already handles, and not later as `undefined` inside a component.

function invalid(): ApiError {
  return new ApiError('invalid_response');
}

export function decodeJob(value: unknown): Job {
  if (!isRecord(value)) {
    throw invalid();
  }
  const { id, name, current_status, created_at, updated_at } = value;
  if (
    typeof id !== 'number' ||
    typeof name !== 'string' ||
    !isJobStatusType(current_status) ||
    typeof created_at !== 'string' ||
    typeof updated_at !== 'string'
  ) {
    throw invalid();
  }
  return { id, name, current_status, created_at, updated_at };
}

export function decodeJobPage(value: unknown): Page<Job> {
  if (!isRecord(value) || !Array.isArray(value.results)) {
    throw invalid();
  }
  return {
    next: cursorFromLink(value.next),
    previous: cursorFromLink(value.previous),
    results: value.results.map(decodeJob),
  };
}

/**
 * Take the `cursor` value out of a pagination link.
 *
 * The link is an absolute URL built from the scheme and host Django sees
 * behind nginx, which need not be the ones the browser used, so it is never
 * followed: the client sends the cursor back on its own relative URL.
 *
 * @returns The cursor, or `null` when there is no such page.
 */
export function cursorFromLink(link: unknown): string | null {
  if (link === null || link === undefined) {
    return null;
  }
  if (typeof link !== 'string') {
    throw invalid();
  }
  let cursor: string | null;
  try {
    cursor = new URL(link, window.location.origin).searchParams.get('cursor');
  } catch {
    throw invalid();
  }
  if (cursor === null) {
    throw invalid();
  }
  return cursor;
}
