/** The states a job can be in, in the order the status menu lists them. */
export const JOB_STATUSES = ['PENDING', 'RUNNING', 'COMPLETED', 'FAILED'] as const;

export type JobStatusType = (typeof JOB_STATUSES)[number];

export function isJobStatusType(value: unknown): value is JobStatusType {
  return JOB_STATUSES.some((status) => status === value);
}

/** A job as `GET /api/jobs/` returns it. Timestamps are ISO 8601 strings. */
export type Job = Readonly<{
  id: number;
  name: string;
  current_status: JobStatusType;
  created_at: string;
  updated_at: string;
}>;

/**
 * One page of a cursor-paginated list. `next` and `previous` are the cursor
 * values only (not the URLs the API sends), or `null` at either end.
 */
export type Page<T> = Readonly<{
  next: string | null;
  previous: string | null;
  results: readonly T[];
}>;
