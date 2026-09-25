import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";

// Self-hosted (see fonts/LICENSES.md): next/font/google downloads at build
// time, and that download failed CI three times.
const inter = localFont({
    src: "./fonts/inter-latin-wght.woff2",
    weight: "100 900",
    variable: "--font-inter",
});

const jetbrainsMono = localFont({
    src: "./fonts/jetbrains-mono-latin-wght.woff2",
    weight: "100 800",
    variable: "--font-jetbrains-mono",
});

const chakra = localFont({
    src: [
        { path: "./fonts/chakra-petch-latin-600.woff2", weight: "600" },
        { path: "./fonts/chakra-petch-latin-700.woff2", weight: "700" },
    ],
    variable: "--font-chakra",
});

const TITLE = "Aegis — support agents that stop for a human";
// ≤125 chars: social previews truncate around there, search results around 155.
const DESCRIPTION =
    "AI agents triage support tickets and investigate a live database, then pause for human approval before any action runs.";

const OG_IMAGE = { url: "/og.png", width: 1200, height: 630, alt: "Aegis — the agents do the investigation, you release the action" };

export const metadata: Metadata = {
    metadataBase: new URL("https://aegis.edycu.dev"),
    title: TITLE,
    description: DESCRIPTION,
    icons: {
        icon: [
            { url: "/icon.svg", type: "image/svg+xml" },
            { url: "/favicon-32.png", type: "image/png", sizes: "32x32" },
        ],
        apple: { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    },
    openGraph: {
        title: TITLE,
        description: DESCRIPTION,
        siteName: "Aegis",
        locale: "en_US",
        type: "website",
        images: [OG_IMAGE],
    },
    twitter: {
        card: "summary_large_image",
        title: TITLE,
        description: DESCRIPTION,
        images: [OG_IMAGE.url],
    },
};

export const viewport: Viewport = {
    themeColor: "#0a0e17",
    colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} ${chakra.variable}`} suppressHydrationWarning>
            <body className="antialiased" suppressHydrationWarning>{children}</body>
        </html>
    );
}

