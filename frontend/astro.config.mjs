// @ts-check
import { defineConfig } from 'astro/config';
import node from '@astrojs/node';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  output: 'server', // Server-side rendering enabled
  adapter: node({
    mode: 'standalone'
  }),
  server: {
    port: 4323
  },
  vite: {
    plugins: [tailwindcss()]
  }
});