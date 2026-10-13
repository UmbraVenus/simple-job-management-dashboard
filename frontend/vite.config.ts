import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// TODO: `npm run dev` has no API proxy. Deferred: the app is built and run
//  through Docker Compose, where nginx proxies /api. Fix: `server.proxy` for
//  `/api` to the `make up` stack (http://localhost:8080).
export default defineConfig({
  plugins: [react()],
});
