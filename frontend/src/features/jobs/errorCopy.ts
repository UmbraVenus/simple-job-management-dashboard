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

/** True when the API said the job is not there: deleted elsewhere since this page loaded. */
export function isJobGone(error: Error): boolean {
  return error instanceof ApiError && error.status === 404;
}
