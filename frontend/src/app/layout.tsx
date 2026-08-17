import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
    subsets: ["latin"],
    weight: ["400", "500", "600", "700", "800"],
    variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
    subsets: ["latin"],
    weight: ["400", "500"],
    variable: "--font-jetbrains-mono",
});

const TITLE = "Aegis — Autonomous Enterprise Action Engine";
const DESCRIPTION =
    "Multi-agent AI system with Human-in-the-Loop approval, dynamic model routing, semantic caching, and real-time observability.";

export const metadata: Metadata = {
    title: TITLE,
    description: DESCRIPTION,
    icons: { icon: { url: "/favicon.svg", type: "image/svg+xml" } },
    openGraph: {
        title: TITLE,
        description: DESCRIPTION,
        siteName: "Aegis",
        locale: "en_US",
        type: "website",
    },
    twitter: {
        card: "summary_large_image",
        title: TITLE,
        description: DESCRIPTION,
    },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
            <body className="antialiased" suppressHydrationWarning>{children}</body>
        </html>
    );
}

