import type { Metadata } from "next";
import "./globals.css";
import "./manu-theme.css";
import "./cinematic.css";
import "./bridge.css";
import "./google-home.css";
import GoogleHome from "@/components/google-home";

export const metadata: Metadata = { title: "Manu AI — Personal Discovery Intelligence", description: "Your private, intelligent discovery system" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><GoogleHome />{children}</body></html>;
}
