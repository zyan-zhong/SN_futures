import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    base: "/terminal/",
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy: {
        "/api": {
          target: env.VITE_API_BASE_URL || "http://127.0.0.1:8765",
          changeOrigin: true
        }
      }
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
      chunkSizeWarningLimit: 1200,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules/react/") || id.includes("node_modules/react-dom/") || id.includes("node_modules/scheduler/")) return "react-vendor";
            if (id.includes("node_modules/echarts") || id.includes("node_modules/zrender") || id.includes("node_modules/echarts-for-react")) return "echarts";
            if (id.includes("node_modules")) return "vendor";
          }
        }
      }
    }
  };
});
