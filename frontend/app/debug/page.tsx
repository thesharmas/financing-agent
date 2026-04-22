'use client'

import { useEffect, useState } from 'react'
import { usePrivy, useWallets } from '@privy-io/react-auth'
import {
  createPublicClient,
  createWalletClient,
  custom,
  formatUnits,
  http,
  parseUnits,
  type Address,
  type Hash,
} from 'viem'
import { tempoTestnet, isChainConfigured } from '@/lib/chain'
import {
  ERC20_ABI,
  TREASURY_ADDRESS,
  USDC_ADDRESS,
  USDC_DECIMALS,
} from '@/lib/usdc'

type VerifyResult = {
  ok: boolean
  from?: string
  to?: string
  amount?: string
  status?: string
  blockNumber?: string
  error?: string
}

export default function Page() {
  const { ready, authenticated, login, logout, user } = usePrivy()
  const { wallets } = useWallets()

  const embeddedWallet = wallets.find((w) => w.walletClientType === 'privy')
  const userAddress = embeddedWallet?.address as Address | undefined

  const [balance, setBalance] = useState<string>('—')
  const [amount, setAmount] = useState<string>('1')
  const [recipient, setRecipient] = useState<string>(TREASURY_ADDRESS || '')
  const [sending, setSending] = useState(false)
  const [txHash, setTxHash] = useState<Hash | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [verifyInput, setVerifyInput] = useState<string>('')
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null)

  const configured = isChainConfigured() && !!USDC_ADDRESS && !!TREASURY_ADDRESS

  useEffect(() => {
    if (!userAddress || !configured) return
    const publicClient = createPublicClient({
      chain: tempoTestnet,
      transport: http(),
    })
    publicClient
      .readContract({
        address: USDC_ADDRESS,
        abi: ERC20_ABI,
        functionName: 'balanceOf',
        args: [userAddress],
      })
      .then((raw) => setBalance(formatUnits(raw as bigint, USDC_DECIMALS)))
      .catch((e) => setBalance(`error: ${e.message}`))
  }, [userAddress, txHash, configured])

  async function sendUsdc() {
    setError(null)
    setTxHash(null)
    if (!embeddedWallet || !userAddress) return
    setSending(true)
    try {
      const provider = await embeddedWallet.getEthereumProvider()
      const walletClient = createWalletClient({
        account: userAddress,
        chain: tempoTestnet,
        transport: custom(provider),
      })
      const hash = await walletClient.writeContract({
        address: USDC_ADDRESS,
        abi: ERC20_ABI,
        functionName: 'transfer',
        args: [recipient as Address, parseUnits(amount, USDC_DECIMALS)],
      })
      setTxHash(hash)
      setVerifyInput(hash)
    } catch (e: any) {
      setError(e?.shortMessage || e?.message || String(e))
    } finally {
      setSending(false)
    }
  }

  async function verify() {
    setVerifyResult(null)
    try {
      const res = await fetch('/api/verify', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ tx_hash: verifyInput }),
      })
      setVerifyResult(await res.json())
    } catch (e: any) {
      setVerifyResult({ ok: false, error: e?.message || String(e) })
    }
  }

  if (!ready) return <Shell>Loading…</Shell>

  return (
    <Shell>
      <h1 className="text-2xl font-semibold mb-2">Phase 1 — Privy + Tempo spike</h1>
      <p className="text-sm text-gray-600 mb-6">
        Learning goal: log in, see a wallet, send test USDC, verify server-side.
      </p>

      {!configured && (
        <div className="mb-6 p-3 rounded border border-amber-300 bg-amber-50 text-sm">
          <strong>Config missing.</strong> Copy <code>.env.local.example</code> to{' '}
          <code>.env.local</code> and fill in the Tempo values. See the README.
        </div>
      )}

      {!authenticated ? (
        <button
          className="px-4 py-2 rounded bg-black text-white"
          onClick={() => login()}
        >
          Log in
        </button>
      ) : (
        <div className="space-y-6">
          <Row label="User ID" value={user?.id ?? '—'} />
          <Row label="Wallet address" value={userAddress ?? 'provisioning…'} mono />
          <Row label="Balance" value={`${balance} testUSDC`} />

          <section className="p-4 rounded border bg-white space-y-3">
            <h2 className="font-medium">Send testUSDC</h2>
            <label className="block text-sm">
              <span className="text-gray-600">Recipient</span>
              <input
                className="mt-1 w-full font-mono text-xs border rounded px-2 py-1"
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
              />
            </label>
            <label className="block text-sm">
              <span className="text-gray-600">Amount (testUSDC)</span>
              <input
                className="mt-1 w-32 border rounded px-2 py-1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
            <button
              className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-50"
              disabled={sending || !userAddress || !recipient}
              onClick={sendUsdc}
            >
              {sending ? 'Sending…' : `Send ${amount} testUSDC`}
            </button>
            {txHash && (
              <div className="text-xs font-mono break-all">
                tx: <span className="text-blue-700">{txHash}</span>
              </div>
            )}
            {error && (
              <div className="text-sm text-red-700 whitespace-pre-wrap">{error}</div>
            )}
          </section>

          <section className="p-4 rounded border bg-white space-y-3">
            <h2 className="font-medium">Verify on backend</h2>
            <input
              className="w-full font-mono text-xs border rounded px-2 py-1"
              placeholder="0x…"
              value={verifyInput}
              onChange={(e) => setVerifyInput(e.target.value)}
            />
            <button
              className="px-4 py-2 rounded bg-green-600 text-white disabled:opacity-50"
              disabled={!verifyInput}
              onClick={verify}
            >
              Verify
            </button>
            {verifyResult && (
              <pre className="text-xs bg-gray-900 text-gray-100 p-3 rounded overflow-x-auto">
                {JSON.stringify(verifyResult, null, 2)}
              </pre>
            )}
          </section>

          <button className="text-sm underline text-gray-600" onClick={() => logout()}>
            Log out
          </button>
        </div>
      )}
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="max-w-2xl mx-auto p-6">
      <div className="mt-8">{children}</div>
    </main>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start gap-3 text-sm">
      <span className="w-32 shrink-0 text-gray-500">{label}</span>
      <span className={`${mono ? 'font-mono text-xs' : ''} break-all`}>{value}</span>
    </div>
  )
}
