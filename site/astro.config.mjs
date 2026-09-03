// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

// Tailwind v4 走构建脚本预生成（npm run tw）：@tailwindcss/vite 在 Astro
// 管线里不产出工具类（2026-09 实测），CLI 方式两端一致且稳定。
export default defineConfig({
  site: 'https://pageglean.pages.dev',
  integrations: [react()],
});
