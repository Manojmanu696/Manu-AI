import type { Metadata } from "next";
import "./globals.css";
import "./manu-theme.css";
import "./cinematic.css";
import "./bridge.css";
import "./google-home.css";
import "./manu-modern.css";

export const metadata: Metadata = { title: "Manu AI — Personal Discovery Intelligence", description: "Search the web, discover media, and use your personal taste — from one box." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
