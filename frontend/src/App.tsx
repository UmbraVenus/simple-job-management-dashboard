import { useEffect, useState } from 'react';

// Phase 1 placeholder: proves browser -> nginx -> gunicorn -> Postgres works.
// Replaced by the jobs page in Phase 6.

type BackendHealth = 'checking' | 'healthy' | 'unreachable';

const HEALTH_LABEL: Record<BackendHealth, string> = {
  checking: 'Checking backend…',
  healthy: 'Backend: healthy',
  unreachable: 'Backend: unreachable',
};

export function App() {
  const [health, setHealth] = useState<BackendHealth>('checking');

  useEffect(() => {
    const controller = new AbortController();

    // Relative URL: the same build works behind any host or port.
    fetch('/api/health/', { signal: controller.signal })
      .then((response) => setHealth(response.ok ? 'healthy' : 'unreachable'))
      .catch(() => {
        if (!controller.signal.aborted) {
          setHealth('unreachable');
        }
      });

    return () => controller.abort();
  }, []);

  return (
    <main>
      <h1>Job Management Dashboard</h1>
      <p role="status">{HEALTH_LABEL[health]}</p>
    </main>
  );
}
