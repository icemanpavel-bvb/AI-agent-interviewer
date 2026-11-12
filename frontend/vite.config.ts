import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// В разработке запросы /api проксируются на бэкенд (uvicorn на :8000).
// В Docker то же делает nginx.conf.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
