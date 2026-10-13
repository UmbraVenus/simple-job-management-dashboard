import type { ThemeConfig } from 'antd';

const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export const theme: ThemeConfig = {
  token: {
    // AntD's default blue (#1677ff) under white button text is about 4.1:1,
    // below the 4.5:1 that WCAG AA asks for. These two shades pass.
    colorPrimary: '#0958d9',
    colorError: '#cf1322',
    // Menus and popovers open without animation for users who ask for that.
    // The E2E tests ask for it too, so they never wait on a transition.
    motion: !prefersReducedMotion,
  },
};
