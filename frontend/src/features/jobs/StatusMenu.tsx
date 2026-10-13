import { CheckOutlined, DownOutlined } from '@ant-design/icons';
import { Button, Dropdown } from 'antd';
import type { MenuProps } from 'antd';
import { memo, useMemo } from 'react';

import { JOB_STATUSES, isJobStatusType } from '../../types/job';
import type { Job, JobStatusType } from '../../types/job';
import { STATUS_META } from './statusMeta';

export type StatusMenuProps = Readonly<{
  job: Job;
  /** True while this job's status change is in flight. */
  pending: boolean;
  disabled: boolean;
  onChange: (status: JobStatusType) => void;
}>;

/**
 * "Change status" button that opens a menu of every status.
 *
 * The job's current status is ticked and disabled, so the menu never sends a
 * change to the status the job already has (the API would accept it and log a
 * duplicate entry).
 */
export const StatusMenu = memo(function StatusMenu({ job, pending, disabled, onChange }: StatusMenuProps) {
  const current = job.current_status;
  const items = useMemo<NonNullable<MenuProps['items']>>(
    () =>
      JOB_STATUSES.map((status) => ({
        key: status,
        label: STATUS_META[status].label,
        disabled: status === current,
        icon: status === current ? <CheckOutlined /> : <span className="status-menu__check" />,
      })),
    [current],
  );
  const menu = useMemo<MenuProps>(
    () => ({
      items,
      onClick: ({ key }) => {
        if (isJobStatusType(key) && key !== current) {
          onChange(key);
        }
      },
    }),
    [items, current, onChange],
  );

  return (
    <Dropdown menu={menu} trigger={CLICK} disabled={disabled}>
      <Button
        type="text"
        icon={<DownOutlined />}
        iconPlacement="end"
        loading={pending}
        // Names the job, so a screen reader (and a test) can tell the rows' buttons apart.
        aria-label={`Change status of ${job.name}`}
      >
        Change status
      </Button>
    </Dropdown>
  );
});

const CLICK: ['click'] = ['click'];
