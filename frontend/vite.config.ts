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
      // Les routes historiques retirent /api ; /api/v1 est conservé pour l'API versionnée.
      proxy: {
        '/api': {
          target: backend,
          changeOrigin: true,
          rewrite: (path) => path.startsWith('/api/v1/') ? path : path.replace(/^\/api/, ''),
        },
      },
    },
  };
});
