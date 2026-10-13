import type { JobStatusType } from '../../types/job';

type StatusMeta = Readonly<{
  label: string;
  /** Tag colours. Text is at least 4.5:1 against its background. */
  tag: Readonly<{ color: string; background: string; borderColor: string }>;
}>;

// A Record over the union: adding a status to JOB_STATUSES is a compile error
// here until it has a label and colours.
export const STATUS_META: Readonly<Record<JobStatusType, StatusMeta>> = {
  PENDING: { label: 'Pending', tag: { color: 'rgba(0, 0, 0, 0.88)', background: '#fafafa', borderColor: '#d9d9d9' } },
  RUNNING: { label: 'Running', tag: { color: '#0958d9', background: '#e6f4ff', borderColor: '#91caff' } },
  COMPLETED: { label: 'Completed', tag: { color: '#237804', background: '#f6ffed', borderColor: '#b7eb8f' } },
  FAILED: { label: 'Failed', tag: { color: '#cf1322', background: '#fff1f0', borderColor: '#ffa39e' } },
};
