import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Japanbuild-BIM3D — 建築確認プレチェック支援",
  description:
    "建築確認プレチェック支援 (1차 스크리닝). 最終判断は有資格者・審査機関が行います. 本ツールは判定を確定しません.",
};

const DISCLAIMER_JA =
  "本ツールは建築確認プレチェック支援であり、判定を確定しません。最終判断は有資格者（建築士）・審査機関が行います。";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ja"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <div className="flex-1">{children}</div>
        <footer className="border-t px-4 py-3 text-xs text-muted-foreground">
          {DISCLAIMER_JA}
        </footer>
      </body>
    </html>
  );
}
