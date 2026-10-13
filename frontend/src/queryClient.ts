import { QueryClient } from '@tanstack/react-query';

// No automatic retry of the list request. TanStack's default is three more
// attempts with a growing delay, and behind a stopped backend each attempt
// waits for nginx to give up, so the page would sit on its spinner for most of
// a minute. One attempt, then the error with a Retry button the user controls.
// Mutations are never retried either (TanStack's default), so a create is not
// sent twice behind the user's back.
export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});
