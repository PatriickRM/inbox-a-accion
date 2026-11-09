import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, /api/* se reenvia a la API de FastAPI (puerto 8000).
// Asi el navegador habla con un solo origen y no hace falta configurar CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/api/, ""),
      },
    },
  },
});
