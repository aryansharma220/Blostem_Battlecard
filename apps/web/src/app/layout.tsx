import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Battlecard Generator",
  description: "Fintech competitor intelligence battlecards in under 60 seconds",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
