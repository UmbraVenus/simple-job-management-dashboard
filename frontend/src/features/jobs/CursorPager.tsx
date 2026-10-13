import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import { Button } from 'antd';
import { memo } from 'react';

export type CursorPagerProps = Readonly<{
  /** Accessible name of the navigation landmark; must differ between pagers on one page. */
  label: string;
  hasPrevious: boolean;
  hasNext: boolean;
  /** True while a page is loading: both buttons are disabled. */
  disabled: boolean;
  onPrevious: () => void;
  onNext: () => void;
}>;

/**
 * Previous / Next for a cursor-paginated list.
 *
 * AntD's own pagination needs a total row count to draw page numbers; a cursor
 * API never counts, so all it can offer is the two neighbouring pages.
 */
export const CursorPager = memo(function CursorPager(props: CursorPagerProps) {
  const { label, hasPrevious, hasNext, disabled, onPrevious, onNext } = props;
  return (
    <nav className="cursor-pager" aria-label={label}>
      <Button icon={<LeftOutlined />} disabled={disabled || !hasPrevious} onClick={onPrevious}>
        Previous
      </Button>
      <Button icon={<RightOutlined />} iconPlacement="end" disabled={disabled || !hasNext} onClick={onNext}>
        Next
      </Button>
    </nav>
  );
});
