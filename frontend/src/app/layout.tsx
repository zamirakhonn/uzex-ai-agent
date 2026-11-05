import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "UZEX Insight — Dataset Q&A",
  description: "Answers only from the UZEX exchange dataset. No hallucinations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body className="antialiased">{children}</body>
    </html>
  );
}
