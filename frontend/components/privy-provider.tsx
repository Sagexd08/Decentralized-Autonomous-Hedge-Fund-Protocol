"use client"

import { PrivyProvider } from "@privy-io/react-auth"

const PRIVY_APP_ID = process.env.NEXT_PUBLIC_PRIVY_APP_ID!

export function AppPrivyProvider({ children }: { children: React.ReactNode }) {
  return (
    <PrivyProvider
      appId={PRIVY_APP_ID}
      config={{
        appearance: {
          theme: "dark",
          accentColor: "#f59e0b",
          logo: undefined,
        },
        loginMethods: ["wallet", "email"],
        embeddedWallets: {
          ethereum: { createOnLogin: "users-without-wallets" },
        },
      }}
    >
      {children}
    </PrivyProvider>
  )
}
