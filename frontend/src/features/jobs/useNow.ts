import { useSyncExternalStore } from 'react';

const TICK_MS = 30_000;

// One timer for the whole page, however many components read the clock. It
// runs only while something is subscribed.
const listeners = new Set<() => void>();
let timer: number | undefined;
let now = Date.now();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  if (timer === undefined) {
    now = Date.now();
    timer = window.setInterval(() => {
      now = Date.now();
      listeners.forEach((notify) => notify());
    }, TICK_MS);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      window.clearInterval(timer);
      timer = undefined;
    }
  };
}

function getSnapshot(): number {
  return now;
}

/**
 * The current time in milliseconds, refreshed every 30 seconds.
 *
 * Only the components that call this re-render on a tick, so a relative label
 * ("5 min ago") stays current without re-rendering the table around it.
 */
export function useNow(): number {
  return useSyncExternalStore(subscribe, getSnapshot);
}
