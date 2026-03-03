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

export const metadata: Metadata = {
    title: "Aegis — Autonomous Enterprise Action Engine",
    description: "Multi-agent AI system with Human-in-the-Loop approval, dynamic model routing, semantic caching, and real-time observability.",
    icons: { icon: { url: "/favicon.svg", type: "image/svg+xml" } },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
            <body className="antialiased" suppressHydrationWarning>{children}</body>
        </html>
    );
}

