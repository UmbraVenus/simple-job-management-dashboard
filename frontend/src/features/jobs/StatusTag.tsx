import { Tag } from 'antd';
import { memo } from 'react';

import type { JobStatusType } from '../../types/job';
import { STATUS_META } from './statusMeta';

export type StatusTagProps = Readonly<{ status: JobStatusType }>;

/** A job's status as a coloured tag. The text carries the meaning; the colour only repeats it. */
export const StatusTag = memo(function StatusTag({ status }: StatusTagProps) {
  const { label, tag } = STATUS_META[status];
  return <Tag style={tag}>{label}</Tag>;
});
