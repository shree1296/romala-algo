import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { spawn } from 'node:child_process';

function startBackend() {
  // Don't start if already running
  const child = spawn('python3', ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000'], {
    cwd: fileURLToPath(new URL('./backend', import.meta.url)),
    stdio: 'ignore',
    detached: false,
  });
  child.on('error', () => {});
  return () => { try { child.kill() } catch {} };
}

export default defineConfig({
  plugins: [
    {
      name: 'start-backend',
      configureServer(server) {
        const cleanup = startBackend();
        server.httpServer?.on('close', cleanup);
      },
    },
    react(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
});
