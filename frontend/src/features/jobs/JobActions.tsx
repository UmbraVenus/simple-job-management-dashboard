import { memo, useCallback } from 'react';

import type { Job, JobStatusType } from '../../types/job';
import { DeleteJobButton } from './DeleteJobButton';
import { useChangeStatus, useDeleteJob } from './hooks';
import { StatusMenu } from './StatusMenu';

export type JobActionsProps = Readonly<{ job: Job }>;

/**
 * The controls of one table row.
 *
 * Both requests live here, in the row, so a request in flight re-renders this
 * row only, and while either is running both controls are disabled: a second
 * click cannot send a second request.
 */
export const JobActions = memo(function JobActions({ job }: JobActionsProps) {
  const { mutate: changeStatus, isPending: isChanging } = useChangeStatus(job.id);
  const { mutate: deleteJob, isPending: isDeleting } = useDeleteJob(job.id);
  const busy = isChanging || isDeleting;

  const onChange = useCallback((status: JobStatusType) => changeStatus(status), [changeStatus]);
  const onConfirm = useCallback(() => deleteJob(), [deleteJob]);

  return (
    <div className="job-actions">
      <StatusMenu job={job} pending={isChanging} disabled={busy} onChange={onChange} />
      <DeleteJobButton job={job} pending={isDeleting} disabled={busy} onConfirm={onConfirm} />
    </div>
  );
});
