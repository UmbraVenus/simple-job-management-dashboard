import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { App } from 'antd';
import { useCallback, useEffect, useReducer } from 'react';

import { ApiError } from '../../api/client';
import { createJob, deleteJob, listJobs, updateJobStatus } from '../../api/jobs';
import type { Job, JobStatusType } from '../../types/job';
import { failureText, isJobGone, mayHaveChangedJobs } from './errorCopy';
import type { MutationFailure } from './errorCopy';
import { STATUS_META } from './statusMeta';

const jobsKeys = {
  /** Prefix of every cached page; invalidating it marks them all stale. */
  all: ['jobs'] as const,
  page: (cursor: string | null) => ['jobs', cursor] as const,
};

const ERROR_TOAST_SECONDS = 5;

// TODO: the position lives in memory only, so a reload returns to the first
//  page. Deferred: no router in this app and the brief asks for one page. Fix:
//  keep `cursor` in the URL query string and read it back on load.
/** Where the list is: the cursor the API understands, and a page number only the client knows. */
type Position = Readonly<{ cursor: string | null; pageIndex: number }>;

type Move =
  | Readonly<{ type: 'first' }>
  | Readonly<{ type: 'next'; cursor: string }>
  | Readonly<{ type: 'previous'; cursor: string }>;

const FIRST_PAGE: Position = { cursor: null, pageIndex: 0 };

function move(position: Position, action: Move): Position {
  switch (action.type) {
    case 'first':
      // Same object when already there, so React skips the re-render.
      return position.cursor === null ? position : FIRST_PAGE;
    case 'next':
      return { cursor: action.cursor, pageIndex: position.pageIndex + 1 };
    case 'previous':
      return { cursor: action.cursor, pageIndex: Math.max(0, position.pageIndex - 1) };
  }
}

export type JobsPageState = Readonly<{
  jobs: readonly Job[];
  /**
   * Zero-based number of the page on screen. The API never counts rows, so
   * this is the client's own tally of Next and Previous clicks; it drifts if
   * other users add or delete jobs while this one pages.
   */
  pageIndex: number;
  /** A page is being fetched for the first time; `jobs` is empty or still the previous page. */
  isLoadingPage: boolean;
  /** The last fetch failed. `jobs` may still hold the rows from before it. */
  error: Error | null;
  /** False on any later page. A later page that failed to load has no pager, so it needs another way back. */
  isFirstPage: boolean;
  hasNext: boolean;
  hasPrevious: boolean;
  goNext: () => void;
  goPrevious: () => void;
  goFirst: () => void;
  retry: () => void;
}>;

/**
 * The page of jobs on screen and the controls that move it.
 *
 * Each page is cached under its cursor. While the next one loads, the previous
 * rows stay on screen (`isLoadingPage` is true) instead of the table emptying.
 */
export function useJobsPage(): JobsPageState {
  const [position, dispatch] = useReducer(move, FIRST_PAGE);
  const query = useQuery({
    queryKey: jobsKeys.page(position.cursor),
    queryFn: ({ signal }) => listJobs(position.cursor, signal),
    placeholderData: keepPreviousData,
  });

  const showsOwnData = query.data !== undefined && !query.isPlaceholderData;
  // While the next page loads these still describe the page on screen, so the
  // pager keeps its shape; its buttons are disabled until the load ends.
  const next = query.data?.next ?? null;
  const previous = query.data?.previous ?? null;

  // A later page can stop being usable: its cursor went stale (the API answers
  // 404), or its last job was deleted. Both end on the first page.
  const isPageUnusable =
    position.cursor !== null &&
    ((query.error !== null && isJobGone(query.error)) || (showsOwnData && query.data.results.length === 0));
  useEffect(() => {
    if (isPageUnusable) {
      dispatch({ type: 'first' });
    }
  }, [isPageUnusable]);

  const { refetch } = query;
  const goNext = useCallback(() => {
    if (next !== null) {
      dispatch({ type: 'next', cursor: next });
    }
  }, [next]);
  const goPrevious = useCallback(() => {
    if (previous !== null) {
      dispatch({ type: 'previous', cursor: previous });
    }
  }, [previous]);
  const goFirst = useCallback(() => dispatch({ type: 'first' }), []);
  const retry = useCallback(() => void refetch(), [refetch]);

  return {
    jobs: query.data?.results ?? NO_JOBS,
    pageIndex: position.pageIndex,
    isLoadingPage: query.isPending || query.isPlaceholderData,
    error: isPageUnusable ? null : query.error,
    isFirstPage: position.cursor === null,
    hasNext: next !== null,
    hasPrevious: previous !== null,
    goNext,
    goPrevious,
    goFirst,
    retry,
  };
}

// One shared empty array, so "no data yet" does not look like new data on every render.
const NO_JOBS: readonly Job[] = [];

// The three mutations below report their own result as a toast, here and not
// in the component that started them: a deleted job's row is unmounted by the
// time its request settles, and a callback passed to `mutate()` from that row
// would never run.
//
// Each `onSuccess` returns the refetch promise, which keeps `isPending` true
// until the new list is on screen. The control stays disabled for that whole
// time, and what the row shows is always what the server stored.

/**
 * Bring the pages on screen up to date without reporting a failure to do so.
 *
 * Used after a request whose outcome is unknown (timeout, lost response, 5xx):
 * the change may have been stored, so the rows may be out of date. The usual
 * `invalidateQueries` refetch would be wrong here on two counts. If the server
 * is down it fails too and puts a second error (the load alert) next to the
 * toast the user already got; and waiting for it keeps the row's control
 * disabled for as long as the server takes to not answer.
 *
 * So: fetch each page directly and store it only if it arrives. Every page is
 * also marked stale, so the next ordinary refetch (window focus, paging) still
 * happens, and reports its own failure if it has one.
 */
async function reloadQuietly(queryClient: QueryClient): Promise<void> {
  await queryClient.invalidateQueries({ queryKey: jobsKeys.all, refetchType: 'none' });
  const onScreen = queryClient.getQueryCache().findAll({ queryKey: jobsKeys.all, type: 'active' });
  await Promise.all(
    onScreen.map(async (query) => {
      const cursor = query.queryKey[1];
      if (cursor !== null && typeof cursor !== 'string') {
        return;
      }
      const seenAt = query.state.dataUpdatedAt;
      try {
        const page = await listJobs(cursor);
        // Skip if an ordinary refetch stored something while this one was out:
        // that data is at least as new.
        if (query.state.dataUpdatedAt === seenAt) {
          queryClient.setQueryData(jobsKeys.page(cursor), page);
        }
      } catch {
        // Still unreachable. The rows stay as they are, marked stale.
      }
    }),
  );
}

/**
 * @returns A callback that shows the failure toast and then, unless the API
 *   refused the request outright, brings the list up to date. A job that is
 *   gone is a definite answer from a server that is there, so the list is
 *   reloaded and waited for; an unknown outcome gets a quiet reload in the
 *   background, and the control is usable again at once.
 */
function useReportFailure(failure: MutationFailure): (error: Error) => Promise<void> {
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  return useCallback(
    async (error: Error) => {
      void message.error(failureText(failure, error), ERROR_TOAST_SECONDS);
      if (isJobGone(error)) {
        await queryClient.invalidateQueries({ queryKey: jobsKeys.all });
      } else if (mayHaveChangedJobs(error)) {
        void reloadQuietly(queryClient);
      }
    },
    [failure, message, queryClient],
  );
}

/**
 * Create a job, then show the first page, where the new job is the top row.
 *
 * A refusal of the name itself (blank, too long, duplicate) is not reported
 * here: the form shows it under the input.
 *
 * @param onCreated Moves the list to its first page.
 */
export function useCreateJob(onCreated: () => void) {
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  const reportFailure = useReportFailure('createFailed');
  return useMutation({
    mutationFn: createJob,
    onSuccess: async () => {
      // Mark every page stale without refetching the one being left, then
      // load the first page. If it is not cached, mounting it fetches it.
      await queryClient.invalidateQueries({ queryKey: jobsKeys.all, refetchType: 'none' });
      onCreated();
      await queryClient.refetchQueries({ queryKey: jobsKeys.page(null), exact: true });
      void message.success('Job created');
    },
    onError: async (error) => {
      // A refused name is the form's to show; anything else gets the toast.
      if (nameErrorCodeOf(error) === null) {
        await reportFailure(error);
      }
    },
  });
}

/**
 * @returns The API's error code for the name field, or `null` if the failure is not about the name.
 */
export function nameErrorCodeOf(error: Error): string | null {
  return error instanceof ApiError ? error.fieldCode('name') : null;
}

/** Set one job's status. The server appends an entry to the job's status log on every call. */
export function useChangeStatus(jobId: number) {
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  return useMutation({
    mutationFn: (status: JobStatusType) => updateJobStatus(jobId, status),
    onSuccess: async (job) => {
      await queryClient.invalidateQueries({ queryKey: jobsKeys.all });
      void message.success(`Status set to ${STATUS_META[job.current_status].label}`);
    },
    onError: useReportFailure('updateFailed'),
  });
}

/** Delete one job and its status log. */
export function useDeleteJob(jobId: number) {
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  return useMutation({
    mutationFn: () => deleteJob(jobId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: jobsKeys.all });
      void message.success('Job deleted');
    },
    onError: useReportFailure('deleteFailed'),
  });
}
