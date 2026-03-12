import { defineConfig } from 'vite';
import { loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxyTarget = env.VITE_BACKEND_PROXY_TARGET || 'http://127.0.0.1:5000';
  const devPort = Number(env.PORT || 3000);
  const parsePort = (value) => {
    if (!value) return undefined;
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
  };

  const hmrHost = env.VITE_HMR_HOST;
  const hmrProtocol = env.VITE_HMR_PROTOCOL;
  const hmrPath = env.VITE_HMR_PATH;
  const hmrPort = parsePort(env.VITE_HMR_PORT);
  const hmrClientPort = parsePort(env.VITE_HMR_CLIENT_PORT);
  const hmrDisabled = String(env.VITE_DISABLE_HMR || '').toLowerCase() === 'true';
  const hasHmrOverrides = Boolean(hmrHost || hmrProtocol || hmrPath || hmrPort || hmrClientPort);

  const hmrConfig = hmrDisabled
    ? false
    : hasHmrOverrides
      ? {
          ...(hmrHost ? { host: hmrHost } : {}),
          ...(hmrProtocol ? { protocol: hmrProtocol } : {}),
          ...(hmrPath ? { path: hmrPath } : {}),
          ...(hmrPort ? { port: hmrPort } : {}),
          ...(hmrClientPort ? { clientPort: hmrClientPort } : {}),
        }
      : undefined;

  return {
    plugins: [react()],

    server: {
      // Allow access from LAN and remote dev domains.
      host: '0.0.0.0',
      port: devPort,
      strictPort: true,

      /**
       * Fix: Vite blocks unknown hosts by default (DNS-rebinding protection).
       * Allow ngrok + known custom domains.
       */
      allowedHosts: ['.ngrok-free.dev', 'awegen.online', '.awegen.online'],
      hmr: hmrConfig,

      /**
       * Your frontend calls /api/... and Vite forwards it to Flask.
       * This lets your ngrok URL work without changing frontend API URLs.
       */
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
      },
    },

    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },

    build: {
      outDir: 'build',
      sourcemap: true,
    },
  };
});
