import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, forward /api to the local FastAPI server (uvicorn api.index:app --port 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
