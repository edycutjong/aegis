import type { Metadata, Viewport } from "next";
import { Chakra_Petch, Inter, JetBrains_Mono } from "next/font/google";
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

const chakra = Chakra_Petch({
    subsets: ["latin"],
    weight: ["600", "700"],
    variable: "--font-chakra",
});

const TITLE = "Aegis — support agents that stop for a human";
const DESCRIPTION =
    "A LangGraph multi-agent support desk: agents triage, investigate a live database and propose one action — then pause at a human approval gate before anything executes.";

export const metadata: Metadata = {
    title: TITLE,
    description: DESCRIPTION,
    icons: { icon: { url: "/icon.svg", type: "image/svg+xml" } },
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

