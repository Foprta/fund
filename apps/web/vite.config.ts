/// <reference types="vitest/config" />

import path from "node:path";
import { fileURLToPath } from "node:url";
import { cloudflare } from "@cloudflare/vite-plugin";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import vike from "vike/plugin";
import { defineConfig } from "vite";

const dirname =
  typeof __dirname !== "undefined"
    ? __dirname
    : path.dirname(fileURLToPath(import.meta.url));

const isTest = process.env.VITEST === "true";

export default defineConfig({
  plugins: [
    ...(isTest ? [] : [cloudflare({ viteEnvironment: { name: "ssr" } })]),
    vike(),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.join(dirname, "."),
    },
  },
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          environment: "node",
          include: ["lib/**/*.test.ts"],
        },
      },
    ],
  },
});
