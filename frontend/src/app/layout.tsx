import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { TopBar, BottomNav } from "@/components/nav";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "korb.guru — Smart grocery shopping",
  description:
    "Price comparison, recipes, and shopping lists for Swiss supermarkets",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "korb.guru — Smart grocery shopping",
    description:
      "Price comparison, recipes, and shopping lists for Swiss supermarkets",
    siteName: "korb.guru",
    locale: "en",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={`${inter.className} bg-[#0a0a0a] text-white antialiased`}
      >
        <TopBar />
        <div className="pb-20">{children}</div>
        <BottomNav />
      </body>
    </html>
  );
}
