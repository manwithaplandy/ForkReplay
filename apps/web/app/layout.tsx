import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ForkReplay",
  description: "Fork and replay captured AI agent conversations.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
