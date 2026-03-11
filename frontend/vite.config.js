import { defineConfig } from 'vite';
import { loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxyTarget = env.VITE_BACKEND_PROXY_TARGET || 'http://127.0.0.1:5000';

  return {
    plugins: [react()],

    server: {
      // Allow access from LAN + ngrok
      host: '0.0.0.0',
      port: 3000,

      /**
       * Fix: Vite blocks unknown hosts by default (DNS-rebinding protection).
       * Allow ngrok domains:
       * - '.ngrok-free.dev' covers any random subdomain ngrok gives you.
       */
      allowedHosts: ['.ngrok-free.dev'],

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
