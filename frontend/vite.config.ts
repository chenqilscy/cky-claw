/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/__tests__/setup.ts'],
    testTimeout: 30000,
    include: ['src/__tests__/**/*.test.{ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**'],
    css: false,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            // antd 生态（含 @ant-design、rc-* 全部子包）— 必须在 react 核心之前匹配
            if (id.includes('/antd/') || id.includes('/@ant-design/') || id.includes('/rc-')) {
              return 'vendor-antd';
            }
            // React 核心 — 精确匹配包名边界，避免误匹配 rc-* 内嵌 react
            if (/[\\/]node_modules[\\/](react-dom|react|scheduler)[\\/]/.test(id)) {
              return 'vendor-react';
            }
            if (id.includes('echarts')) {
              return 'vendor-charts';
            }
            if (id.includes('react-syntax-highlighter') || id.includes('react-markdown') || id.includes('remark')) {
              return 'vendor-markdown';
            }
            if (id.includes('@xyflow')) {
              return 'vendor-flow';
            }
            if (id.includes('@tanstack')) {
              return 'vendor-query';
            }
          }
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/otlp': {
        target: 'http://localhost:4318',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/otlp/, ''),
      },
    },
  },
});
