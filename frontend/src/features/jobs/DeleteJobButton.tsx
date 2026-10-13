import { DeleteOutlined } from '@ant-design/icons';
import { Button, Popconfirm } from 'antd';
import { memo } from 'react';

import type { Job } from '../../types/job';

export type DeleteJobButtonProps = Readonly<{
  job: Job;
  /** True while this job's delete is in flight. */
  pending: boolean;
  disabled: boolean;
  onConfirm: () => void;
}>;

const DANGER = { danger: true } as const;

/** Bin button that asks for confirmation before deleting: a delete cannot be undone. */
export const DeleteJobButton = memo(function DeleteJobButton(props: DeleteJobButtonProps) {
  const { job, pending, disabled, onConfirm } = props;
  return (
    <Popconfirm
      title="Delete this job?"
      description={
        <span className="delete-confirm__text">
          “{job.name}” and its status history will be deleted. This can’t be undone.
        </span>
      }
      okText="Delete"
      cancelText="Cancel"
      okButtonProps={DANGER}
      placement="topRight"
      disabled={disabled}
      onConfirm={onConfirm}
    >
      <Button
        type="text"
        danger
        icon={<DeleteOutlined />}
        loading={pending}
        disabled={disabled}
        title="Delete"
        aria-label={`Delete ${job.name}`}
      />
    </Popconfirm>
  );
});
