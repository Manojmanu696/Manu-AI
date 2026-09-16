import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Manu AI", description: "Your personal discovery system" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

