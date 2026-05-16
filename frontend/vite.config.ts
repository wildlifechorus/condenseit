import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';
import tailwindcss from '@tailwindcss/vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig(({ mode }) => {
  const isPwa = mode === 'pwa';

  return {
    plugins: [
      preact(),
      tailwindcss(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['icon.svg'],
        workbox: {
          globPatterns: ['**/*.{js,css,html,svg}'],
          /**
           * digest-data.json must NOT be in the precache manifest.
           * revision:null told Workbox "this URL is already versioned" so it
           * cached the file forever and never re-fetched it on new deploys.
           * Nginx already serves it with Cache-Control: no-store, so online
           * fetches always hit the network; the NetworkFirst runtime rule
           * below provides an offline fallback.
           */
          additionalManifestEntries: [],
          runtimeCaching: isPwa
            ? [
                {
                  /**
                   * NetworkFirst for digest-data.json: always fetch fresh
                   * content when online; fall back to cache when offline.
                   */
                  urlPattern: /\/digest-data\.json$/,
                  handler: 'NetworkFirst',
                  options: {
                    cacheName: 'digest-data-cache',
                    networkTimeoutSeconds: 10,
                    expiration: { maxEntries: 1, maxAgeSeconds: 86400 },
                  },
                },
              ]
            : [],
        },
        manifest: {
          name: 'CondenseIt Digest',
          short_name: 'Digest',
          description: 'Personal AI news digest',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          background_color: '#f8fafc',
          theme_color: '#0d9488',
          icons: [
            {
              src: '/icon.svg',
              sizes: 'any',
              type: 'image/svg+xml',
              purpose: 'any maskable',
            },
          ],
        },
      }),
    ],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:8899',
          changeOrigin: true,
        },
      },
    },
    build: {
      /**
       * PWA builds go to data/pwa-dist (deployed to nginx).
       * Normal builds go to dist/ (served by FastAPI).
       */
      outDir: isPwa ? '../data/pwa-dist' : 'dist',
      emptyOutDir: true,
    },
  };
});
