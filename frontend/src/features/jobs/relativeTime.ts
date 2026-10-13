const MINUTE_MS = 60_000;

// Built once: constructing an Intl formatter is far more expensive than using
// one. `undefined` means the browser's own locale and time zone.
const TIME_FORMAT = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' });
const DAY_FORMAT = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' });
const DAY_YEAR_FORMAT = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
const FULL_FORMAT = new Intl.DateTimeFormat(undefined, { dateStyle: 'full', timeStyle: 'long' });

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/**
 * A short label for a moment, relative to now: "Just now", "5 min ago",
 * "Today, 9:41 PM", "Yesterday, 9:41 PM", "Oct 3, 9:41 PM", "Oct 3, 2025".
 *
 * @param then The moment to describe. Must be a valid date.
 * @param now The current time, passed in so the function stays pure.
 */
export function relativeLabel(then: Date, now: Date): string {
  // A server clock slightly ahead of the browser's gives a negative
  // difference; that reads as "Just now" too.
  const elapsed = now.getTime() - then.getTime();
  if (elapsed < MINUTE_MS) {
    return 'Just now';
  }
  if (elapsed < 60 * MINUTE_MS) {
    return `${Math.floor(elapsed / MINUTE_MS)} min ago`;
  }
  const time = TIME_FORMAT.format(then);
  if (isSameDay(then, now)) {
    return `Today, ${time}`;
  }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (isSameDay(then, yesterday)) {
    return `Yesterday, ${time}`;
  }
  if (then.getFullYear() === now.getFullYear()) {
    return `${DAY_FORMAT.format(then)}, ${time}`;
  }
  return DAY_YEAR_FORMAT.format(then);
}

/** The full date and time, for a tooltip. */
export function fullLabel(then: Date): string {
  return FULL_FORMAT.format(then);
}
