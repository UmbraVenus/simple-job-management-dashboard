import { Card, Typography } from 'antd';

import { PAGE_SIZE } from '../../api/jobs';
import { CreateJobForm } from './CreateJobForm';
import { CursorPager } from './CursorPager';
import { useJobsPage } from './hooks';
import { JobsTable, LoadErrorAlert } from './JobsTable';

const NO_PADDING = { body: { padding: 0 } } as const;
// 30px as designed; smaller on a phone, where three lines of title would push the form down.
const TITLE_STYLE = { margin: 0, fontSize: 'clamp(22px, 6vw, 30px)' } as const;

type RangeText = Readonly<{ short: string; long: string }>;

/**
 * Which rows are on screen, e.g. "21–40". The total appears only on the last
 * page, the one place a cursor API reveals it: there is no `COUNT(*)`.
 *
 * @param pageIndex Zero-based page number, as the client counted it.
 * @param rowCount Rows on this page; at least 1.
 * @param hasNext Whether a later page exists.
 */
function rangeText(pageIndex: number, rowCount: number, hasNext: boolean): RangeText {
  const from = pageIndex * PAGE_SIZE + 1;
  const to = from + rowCount - 1;
  const span = from === to ? String(from) : `${from}–${to}`;
  if (hasNext) {
    return { short: span, long: `Showing ${span}` };
  }
  return {
    short: `${span} of ${to}`,
    long: pageIndex === 0 ? `${to} ${to === 1 ? 'job' : 'jobs'}` : `Showing ${span} of ${to}`,
  };
}

/** The whole application: create a job, see the list, change a status, delete. */
export function JobsPage() {
  const page = useJobsPage();
  const { jobs, isLoadingPage, error } = page;

  const hasRows = jobs.length > 0;
  // With rows on screen the pager is there too; without them it is not, and a
  // later page that failed to load would be a dead end.
  const onFirstPage = page.isFirstPage ? null : page.goFirst;
  const hasPager = page.hasPrevious || page.hasNext;
  // No range while a page loads: the rows on screen are still the last page's.
  const range = hasRows && !isLoadingPage ? rangeText(page.pageIndex, jobs.length, page.hasNext) : null;

  const pager = (label: string) => (
    <CursorPager
      label={label}
      hasPrevious={page.hasPrevious}
      hasNext={page.hasNext}
      disabled={isLoadingPage}
      onPrevious={page.goPrevious}
      onNext={page.goNext}
    />
  );

  return (
    <main className="jobs-page">
      <header className="jobs-page__header">
        <div className="jobs-page__logo" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3l9 4.5-9 4.5-9-4.5L12 3z" />
            <path d="M3 12l9 4.5 9-4.5" />
            <path d="M3 16.5L12 21l9-4.5" opacity="0.7" />
          </svg>
        </div>
        <div>
          <Typography.Title level={1} style={TITLE_STYLE}>
            Job Management Dashboard
          </Typography.Title>
          <Typography.Text type="secondary">Create computational jobs and keep their status up to date.</Typography.Text>
        </div>
      </header>

      <Card styles={NO_PADDING}>
        <div className="jobs-page__toolbar">
          <CreateJobForm onCreated={page.goFirst} />
          {hasPager && (
            <div className="jobs-page__range">
              {range?.short}
              {pager('Pagination, top')}
            </div>
          )}
        </div>

        {/* A refresh failed but the last rows are still here: keep them, and say so. */}
        {error !== null && hasRows && (
          <LoadErrorAlert className="jobs-page__alert" onRetry={page.retry} onFirstPage={null} />
        )}

        <JobsTable jobs={jobs} loading={isLoadingPage} failed={error !== null} onRetry={page.retry} onFirstPage={onFirstPage} />

        {(hasRows || hasPager) && (
          <div className="jobs-page__footer">
            <div className="jobs-page__range" aria-live="polite">
              {range?.long}
            </div>
            {hasPager && pager('Pagination, bottom')}
          </div>
        )}
      </Card>
    </main>
  );
}
