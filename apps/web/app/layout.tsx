import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Crate — your AI crate-digger",
  description:
    "An AI music-discovery companion that optimises for adoption, not feed-scroll.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-spotify-black text-spotify-text font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
