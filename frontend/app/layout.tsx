import React from "react"
import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import './globals.css'

const inter = Inter({ subsets: ["latin"], variable: '--font-inter' });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: '--font-jetbrains' });

export const metadata: Metadata = {
  title: 'DACAP | Decentralized Autonomous Capital Allocation Protocol',
  description: 'On-chain custody. Off-chain intelligence. Governance-controlled capital rotation across AI agents and risk pools.',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

import { GlobalNavbar } from "@/components/global-navbar"
import { AppBackground } from "@/components/visuals/app-background"

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${jetbrainsMono.variable} relative min-h-screen overflow-x-hidden font-sans antialiased`}>
        <AppBackground />
        <div className="relative z-10">
          <GlobalNavbar />
          <main className="pt-16">
            {children}
          </main>
        </div>
        <Analytics />
      </body>
    </html>
  )
}
