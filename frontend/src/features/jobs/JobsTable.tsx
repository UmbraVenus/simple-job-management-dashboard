import { Alert, Button, Empty, Space, Table } from 'antd';
import type { TableColumnsType } from 'antd';
import { memo } from 'react';

import type { Job } from '../../types/job';
import { JobActions } from './JobActions';
import { RelativeTime } from './RelativeTime';
import { StatusTag } from './StatusTag';

/**
 * A cell re-renders only when its row's job object changed. TanStack Query
 * hands back the same object for a job whose data is unchanged after a
 * refetch, so changing one job's status re-renders one row, not the page.
 */
function hasJobChanged(job: Job, previous: Job): boolean {
  return job !== previous;
}

// Defined once at module level: a new array on every render would make the
// table treat every column as changed.
const COLUMNS: TableColumnsType<Job> = [
  {
    title: 'Name',
    key: 'name',
    ellipsis: true,
    shouldCellUpdate: hasJobChanged,
    render: (_value, job) => (
      <span className="job-name" title={job.name}>
        {job.name}
      </span>
    ),
  },
  {
    title: 'Status',
    key: 'status',
    width: 128,
    shouldCellUpdate: hasJobChanged,
    render: (_value, job) => <StatusTag status={job.current_status} />,
  },
  {
    title: 'Created',
    key: 'created',
    width: 180,
    shouldCellUpdate: hasJobChanged,
    render: (_value, job) => <RelativeTime iso={job.created_at} />,
  },
  {
    title: 'Updated',
    key: 'updated',
    width: 180,
    shouldCellUpdate: hasJobChanged,
    render: (_value, job) => <RelativeTime iso={job.updated_at} />,
  },
  {
    title: 'Actions',
    key: 'actions',
    width: 208,
    shouldCellUpdate: hasJobChanged,
    render: (_value, job) => <JobActions job={job} />,
  },
];

/** Below this width the table scrolls sideways inside its card instead of squeezing the name column away. */
const SCROLL = { x: 900 } as const;

export type JobsTableProps = Readonly<{
  jobs: readonly Job[];
  /** A page is loading: the rows (if any) are dimmed under a spinner. */
  loading: boolean;
  /** The list could not be loaded and there are no rows to show in its place. */
  failed: boolean;
  onRetry: () => void;
  /** Leaves a later page that failed to load; `null` on the first page. */
  onFirstPage: (() => void) | null;
}>;

/** The jobs on the current page. Paging is the parent's job (`CursorPager`), not the table's. */
export const JobsTable = memo(function JobsTable(props: JobsTableProps) {
  const { jobs, loading, failed, onRetry, onFirstPage } = props;
  return (
    <section aria-label="Jobs" aria-busy={loading}>
      <Table<Job>
        rowKey="id"
        columns={COLUMNS}
        dataSource={jobs}
        loading={loading}
        pagination={false}
        scroll={SCROLL}
        locale={{ emptyText: emptyContent(loading, failed, onRetry, onFirstPage) }}
      />
    </section>
  );
});

function emptyContent(loading: boolean, failed: boolean, onRetry: () => void, onFirstPage: (() => void) | null) {
  if (loading) {
    // Room for the spinner; "no jobs" would be a claim nobody has checked yet.
    return <div className="jobs-table__placeholder" />;
  }
  if (failed) {
    return <LoadErrorAlert onRetry={onRetry} onFirstPage={onFirstPage} />;
  }
  return (
    <Empty
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description={
        <>
          <strong>No jobs yet</strong>
          <br />
          Enter a job name above and click Create job to start your first one.
        </>
      }
    />
  );
}

export type LoadErrorAlertProps = Readonly<{
  onRetry: () => void;
  /** Adds a "First page" button next to Retry; `null` leaves it out. */
  onFirstPage: (() => void) | null;
  className?: string;
}>;

/** "Couldn't load jobs" with a Retry button, and a way back to the first page when given one. */
export function LoadErrorAlert({ onRetry, onFirstPage, className }: LoadErrorAlertProps) {
  return (
    <Alert
      {...(className === undefined ? {} : { className })}
      type="error"
      showIcon
      title="Couldn’t load jobs"
      description="Something went wrong while fetching the list. Check your connection and try again."
      action={
        <Space>
          {onFirstPage !== null && <Button onClick={onFirstPage}>First page</Button>}
          <Button onClick={onRetry}>Retry</Button>
        </Space>
      }
      style={LEFT_ALIGNED}
    />
  );
}

const LEFT_ALIGNED = { textAlign: 'left' } as const;
