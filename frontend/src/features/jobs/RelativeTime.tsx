import { memo } from 'react';

import { fullLabel, relativeLabel } from './relativeTime';
import { useNow } from './useNow';

export type RelativeTimeProps = Readonly<{
  /** An ISO 8601 timestamp, as the API sends it. */
  iso: string;
}>;

/** A timestamp as a short relative label that keeps itself current, with the full date as a tooltip. */
export const RelativeTime = memo(function RelativeTime({ iso }: RelativeTimeProps) {
  const now = useNow();
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) {
    // Not a date the browser can read: show what the API sent.
    return <span>{iso}</span>;
  }
  return (
    <time dateTime={iso} title={fullLabel(then)}>
      {relativeLabel(then, new Date(now))}
    </time>
  );
});
