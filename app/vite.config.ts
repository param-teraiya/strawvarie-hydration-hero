import { defineConfig } from "vite";
import { resolve } from "node:path";

// Two windows = two HTML entry points. Tauri serves the built `dist/` folder,
// so character art in `public/` ends up at `dist/characters/...` and is
// fetched at runtime with a relative URL.
export default defineConfig({
  root: ".",
  clearScreen: false,
  server: { port: 5173, strictPort: true },
  build: {
    target: "es2021",
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        overlay: resolve(__dirname, "overlay.html"),
      },
    },
  },
});
