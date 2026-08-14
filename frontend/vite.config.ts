import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build output goes to backend/app/static so FastAPI serves the app at / (PRD 7.2).
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../backend/app/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});