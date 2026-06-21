import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Clip Engine",
  description: "Turn one long video into N vertical, captioned, ready-to-post clips.",
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
