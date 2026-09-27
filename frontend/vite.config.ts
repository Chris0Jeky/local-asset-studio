/* Maintainer/CI build only. Output is committed to app/static/ui-dist and served by the unchanged Python server,
   which serves .html/.js/.css only: one stable-named JS module plus one CSS file, no chunks, maps or media. */
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';

const outDir = fileURLToPath(new URL('../app/static/ui-dist', import.meta.url));

export default defineConfig({
  plugins: [vue()],
  base: '/static/ui-dist/',
  define: {
    __VUE_OPTIONS_API__: 'false',
    __VUE_PROD_DEVTOOLS__: 'false',
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false'
  },
  build: {
    outDir,
    emptyOutDir: true,
    target: 'es2022',
    sourcemap: false,
    cssCodeSplit: false,
    modulePreload: false,
    reportCompressedSize: false,
    copyPublicDir: false,
    rollupOptions: {
      input: fileURLToPath(new URL('./src/main.ts', import.meta.url)),
      output: {
        entryFileNames: 'island.js',
        chunkFileNames: 'island-[name].js',
        assetFileNames: 'island[extname]',
        codeSplitting: false
      }
    }
  },
  test: {
    environment: 'happy-dom',
    include: ['tests/**/*.test.ts'],
    // This Windows box has hit Vitest OOM before (MACHINE.md): one forked worker, no parallel files.
    pool: 'forks',
    maxWorkers: 1,
    fileParallelism: false
  }
});
