import type { Metadata } from "next";
import "./globals.css";
import "./manu-theme.css";
import "./cinematic.css";
import "./bridge.css";
import "./google-home.css";
import "./manu-modern.css";
import "./cut.css";

export const metadata: Metadata = { title: "Manu’s Cut", description: "Discover films, series and anime, and keep a personal viewing journal." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
