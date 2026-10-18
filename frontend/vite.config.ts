import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss()],
  base: command === 'build' ? '/static/portal/' : '/',
  build: { outDir: '../app/static/portal', emptyOutDir: true, manifest: true,
    rollupOptions: { input: { portal: 'src/main.tsx', booking: 'src/booking-main.tsx' }, output: { entryFileNames: '[name]-[hash].js',
      chunkFileNames: 'chunks/[name]-[hash].js', assetFileNames: 'assets/[name]-[hash][extname]' } } },
  server: { proxy: { '/api': 'http://127.0.0.1:5000', '/static': 'http://127.0.0.1:5000',
    '^/admin/(?!operations)': 'http://127.0.0.1:5000' } }
}));
