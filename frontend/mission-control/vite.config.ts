import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    emptyOutDir: true,
    outDir: "../../src/dashboard/static/dashboard/mission-control",
    cssCodeSplit: false,
    rollupOptions: {
      input: "src/main.tsx",
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "app-[hash].js",
        assetFileNames: (assetInfo) =>
          assetInfo.name?.endsWith(".css") ? "app.css" : "[name][extname]",
      },
    },
  },
});
