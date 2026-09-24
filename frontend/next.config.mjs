import { fileURLToPath } from "node:url";

const appRoot = fileURLToPath(new URL(".", import.meta.url));
const onVercel = Boolean(process.env.VERCEL);

/** @type {import('next').NextConfig} */
const nextConfig = {
    // Standalone output is for the Docker image; Vercel does its own bundling.
    ...(onVercel ? {} : {
        output: "standalone",
        // The repo root has its own package-lock.json; pin tracing to this app
        // so Next doesn't guess the workspace root (and warn on every build).
        outputFileTracingRoot: appRoot,
    }),
    turbopack: { root: appRoot },
};

export default nextConfig;
