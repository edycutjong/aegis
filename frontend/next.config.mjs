import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    // The repo root has its own package-lock.json; pin tracing to this app so
    // Next doesn't guess the workspace root (and warn on every build).
    outputFileTracingRoot: fileURLToPath(new URL(".", import.meta.url)),
    turbopack: { root: fileURLToPath(new URL(".", import.meta.url)) },
};

export default nextConfig;
