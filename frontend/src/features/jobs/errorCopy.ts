import { ApiError } from '../../api/client';
import copy from './errorCopy.json';

// The API's error `code` picks the text shown here; its English `message` is
// never displayed, so the server can reword it without changing the UI.

const NAME_ERRORS: Readonly<Record<string, string>> = copy.name;

export type MutationFailure = 'createFailed' | 'updateFailed' | 'deleteFailed';

/**
 * @param code An error code for the name field, from the API or from client-side validation.
 * @returns The text to show under the name input; a generic line for a code this build does not know.
 */
export function nameErrorText(code: string): string {
  return NAME_ERRORS[code] ?? copy.fallback;
}

/**
 * @returns The toast text for a failed create, status change or delete.
 */
export function failureText(failure: MutationFailure, error: Error): string {
  return isJobGone(error) ? copy.jobGone : copy[failure];
}

/**
 * True unless the API clearly refused the request and so changed nothing.
 *
 * A 4xx other than 404 is a refusal. Everything else leaves the list on screen
 * possibly out of date: a timeout, a dropped connection or a 5xx can follow a
 * change the server did commit; an unreadable 2xx body means it committed; a
 * 404 means the job is gone.
 */
export function mayHaveChangedJobs(error: Error): boolean {
  const refused = error instanceof ApiError && error.status !== null && error.status >= 400 && error.status < 500;
  return !refused || isJobGone(error);
}

/** True when the API said the job is not there: deleted elsewhere since this page loaded. */
export function isJobGone(error: Error): boolean {
  return error instanceof ApiError && error.status === 404;
}
