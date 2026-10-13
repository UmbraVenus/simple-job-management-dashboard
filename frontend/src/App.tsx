import { QueryClientProvider } from '@tanstack/react-query';
import { App as AntApp, ConfigProvider } from 'antd';

import { JobsPage } from './features/jobs/JobsPage';
import { queryClient } from './queryClient';
import { theme } from './theme';

/** Providers only: the server-state cache, the AntD theme, and AntD's context for toasts. */
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider theme={theme}>
        <AntApp>
          <JobsPage />
        </AntApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
