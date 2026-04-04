import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { UserProvider } from "@/hooks/use-user";
import { Toaster } from "@/components/ui/sonner";
import { generateMetadata, PAGE_METADATA } from "@/lib/metadata";
import { Analytics } from "@vercel/analytics/next";
import { GlobalScrollHandler } from "@/components/global-scroll-handler";
import NavbarClientWrapper from "@/components/NavbarClientWrapper";
import FooterClientWrapper from "@/components/FooterClientWrapper";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = generateMetadata(PAGE_METADATA.home);

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <html lang="en" suppressHydrationWarning>
        <body
          className={`${geistSans.variable} ${geistMono.variable} antialiased min-w-full`}
        >
          <ThemeProvider
            attribute="class"
            defaultTheme="system"
            enableSystem
            disableTransitionOnChange
          >
            <GlobalScrollHandler />
            <UserProvider>
              <NavbarClientWrapper />
              {children}
              <Toaster richColors />
              <Analytics />
              <FooterClientWrapper />
            </UserProvider>
          </ThemeProvider>
        </body>
      </html>
    </>
  );
}
