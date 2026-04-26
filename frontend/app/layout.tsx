import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Cyrus — AI Grading Platform",
  description: "AI-powered teacher grading and student feedback platform. Grade exam papers at scale with OCR and semantic AI.",
  manifest: "/manifest.json",
  themeColor: "#0f0f1a",
  viewport: "width=device-width, initial-scale=1, maximum-scale=1",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased bg-[#0f0f1a] text-white min-h-screen`}>
        {children}
      </body>
    </html>
  );
}
