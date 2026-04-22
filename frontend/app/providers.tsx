'use client'

import { PrivyProvider } from '@privy-io/react-auth'
import { tempoTestnet } from '@/lib/chain'

export function Providers({ children }: { children: React.ReactNode }) {
  const appId = process.env.NEXT_PUBLIC_PRIVY_APP_ID || ''

  return (
    <PrivyProvider
      appId={appId}
      config={{
        loginMethods: ['email', 'google'],
        appearance: { theme: 'light' },
        embeddedWallets: {
          createOnLogin: 'users-without-wallets',
        },
        defaultChain: tempoTestnet,
        supportedChains: [tempoTestnet],
      }}
    >
      {children}
    </PrivyProvider>
  )
}
