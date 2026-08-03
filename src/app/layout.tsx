import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import { SearchProvider } from "@/components/SearchProvider";

import "./globals.css";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-plex-sans",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: {
    default: "LunarForge — a safe, extensible coding agent for real projects",
    template: "%s · LunarForge",
  },
  description:
    "LunarForge inspects your repository, follows root and nested AGENTS.md instructions, plans changes, makes permission-gated edits inside project boundaries, and runs approved commands locally or in Docker.",
};

export const viewport: Viewport = {
  themeColor: "#0b0c0d",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`}>
      <body>
        <a className="skipLink" href="#main">
          Skip to content
        </a>
        <SearchProvider>{children}</SearchProvider>
      </body>
    </html>
  );
}
