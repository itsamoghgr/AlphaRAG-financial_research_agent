import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AlphaRAG",
  description:
    "Financial research agent over SEC filings with citation-backed answers.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="alpharag">
      <body className="bg-app-gradient min-h-screen">{children}</body>
    </html>
  );
}
