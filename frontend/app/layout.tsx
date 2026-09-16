import type { Metadata } from "next";
import "./globals.css";
import "./manu-theme.css";
import "./cinematic.css";
import "./bridge.css";
import ChatQueryBridge from "@/components/chat-query-bridge";

export const metadata: Metadata = { title: "Manu AI — Personal Discovery Intelligence", description: "Your private, intelligent discovery system" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><ChatQueryBridge />{children}</body></html>;
}
