import React from "react"
import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import './globals.css'

const inter = Inter({ subsets: ["latin"], variable: '--font-inter' });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: '--font-jetbrains' });

export const metadata: Metadata = {
  title: 'IRIS Protocol | Decentralized Autonomous Capital Allocation Protocol',
  description: 'On-chain custody. Off-chain intelligence. Governance-controlled capital rotation across AI agents and risk pools.',
  generator: 'v0.app',
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/iris-mark.png', type: 'image/png', sizes: '95x95' },
    ],
    shortcut: '/favicon.ico',
    apple: '/apple-icon.png',
  },
  openGraph: {
    title: 'IRIS Protocol',
    description: 'Where intelligence competes for capital.',
    images: ['/iris-logo.png'],
  },
}

import { GlobalNavbar } from "@/components/global-navbar"
import { AppBackground } from "@/components/visuals/app-background"
import { AppPrivyProvider } from "@/components/privy-provider"

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${jetbrainsMono.variable} relative min-h-screen overflow-x-hidden font-sans antialiased`}>
        <AppPrivyProvider>
          <AppBackground />
          <div className="relative z-10">
            <GlobalNavbar />
            <main className="pt-16">
              {children}
            </main>
          </div>
          <Analytics />
        </AppPrivyProvider>
      </body>
    </html>
  )
}
