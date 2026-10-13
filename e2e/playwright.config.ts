import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  // Fail the run if a stray `test.only` is committed.
  forbidOnly: true,
  // One retry absorbs a transient infrastructure hiccup; a test that needed it
  // is reported as "flaky" instead of silently passing.
  retries: 1,
  reporter: 'list',
  // How long one `expect` keeps re-checking the page (default 5 s). Raised for
  // a slow or busy machine: a passing check returns as soon as it is true, so
  // the extra time is spent only by a test that is failing anyway.
  expect: { timeout: 10_000 },
  use: {
    // Inside the compose network the app is reached by its service name.
    baseURL: process.env.BASE_URL ?? 'http://frontend',
    trace: 'retain-on-failure',
    // The app turns AntD's open/close animations off for this setting, so a
    // test never has to wait for a menu or popover to finish moving.
    reducedMotion: 'reduce',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
