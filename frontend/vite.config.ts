import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // Adresse du backend FastAPI pour le serveur de développement (npm run dev).
  const backend = env.VITE_PROXY_TARGET || 'http://localhost:8000';
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    optimizeDeps: {
      exclude: ['lucide-react'],
    },
    server: {
      // Le navigateur appelle /api/... ; Vite redirige vers le backend en retirant le préfixe /api
      // (le backend expose /auth/login, /alerts, ... sans préfixe). Aucun CORS à configurer en dev.
      proxy: {
        '/api': {
          target: 'http://api:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  };
});
