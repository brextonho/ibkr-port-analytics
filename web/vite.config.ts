import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Inside docker-compose the API lives at http://api:8000; locally at :8000.
const target = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
