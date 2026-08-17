import { defineConfig, configDefaults } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "src"),
        },
    },
    test: {
        environment: "jsdom",
        setupFiles: ["./vitest.setup.ts"],
        globals: true,
        // Playwright owns everything under e2e/ (see playwright.config.ts) — Vitest
        // must not try to collect those specs too, or it fails outright.
        exclude: [...configDefaults.exclude, "e2e/**"],
        coverage: {
            provider: "v8",
            reporter: ["text", "html"],
            include: ["src/**/*.{ts,tsx}"],
            exclude: [
                ...configDefaults.exclude,
                "src/**/__tests__/**",
                "src/**/*.d.ts",
                // Framework boilerplate: metadata export + <html>/<body> wrapper.
                // Not meaningfully unit-testable in jsdom (nested <html> tags) and
                // carries no branch logic of our own — see report for rationale.
                "src/app/layout.tsx",
            ],
            // The suite genuinely reaches 100% on all four metrics as of this
            // writing (see frontend test report). Set to what's actually
            // achieved, not aspirationally — ratchet down here if a future
            // change legitimately can't hit 100 (e.g. an unreachable branch),
            // rather than disabling the gate.
            thresholds: {
                statements: 100,
                branches: 100,
                functions: 100,
                lines: 100,
            },
        },
    },
});
