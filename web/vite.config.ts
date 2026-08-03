import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base: the bank ships as static files next to the app, so the build has to work
// from any subpath a host happens to serve it from (docs/06 §6.5, "static hosting").
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: { target: "es2022" },
});
