import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `npm run dev` serves the dashboard on :5173 and forwards /api to
// `portfolio serve` on :8000.
const target = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target,
        changeOrigin: true,
      },
    },
  },
});
