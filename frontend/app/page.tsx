'use client'

import { useCallback, useMemo, useRef, useState } from 'react'
import { usePrivy, useWallets } from '@privy-io/react-auth'
import {
  createPublicClient,
  createWalletClient,
  custom,
  http,
  parseUnits,
  type Address,
  type Hash,
} from 'viem'
import { isChainConfigured, tempoTestnet } from '@/lib/chain'
import { ERC20_ABI, TREASURY_ADDRESS, USDC_ADDRESS, USDC_DECIMALS } from '@/lib/usdc'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const PRICE_USDC = process.env.NEXT_PUBLIC_PRICE_USDC || '2'

type Stage = 'idle' | 'paying' | 'waiting' | 'analyzing' | 'done' | 'error'

type StreamEvent =
  | { type: 'run'; data: { run_id: string; gcs_uri: string } }
  | { type: 'text'; data: string }
  | { type: 'tool_use'; data: { name: string; input: Record<string, unknown> } }
  | { type: 'done'; data: { input_tokens: number; output_tokens: number } }
  | { type: 'error'; data: string }

export default function Page() {
  const { ready, authenticated, login, logout } = usePrivy()
  const { wallets } = useWallets()
  const wallet = wallets.find((w) => w.walletClientType === 'privy')
  const userAddress = wallet?.address as Address | undefined

  const [file, setFile] = useState<File | null>(null)
  const [stage, setStage] = useState<Stage>('idle')
  const [error, setError] = useState<string | null>(null)
  const [txHash, setTxHash] = useState<Hash | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<string>('')
  const [toolCalls, setToolCalls] = useState<{ name: string }[]>([])
  const [tokens, setTokens] = useState<{ input: number; output: number } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const configured = isChainConfigured() && !!USDC_ADDRESS && !!TREASURY_ADDRESS

  const analyzeDisabled = useMemo(
    () => !file || !wallet || !configured || stage === 'paying' || stage === 'waiting' || stage === 'analyzing',
    [file, wallet, configured, stage],
  )

  const reset = () => {
    setStage('idle')
    setError(null)
    setTxHash(null)
    setRunId(null)
    setAnalysis('')
    setToolCalls([])
    setTokens(null)
  }

  const handleAnalyze = useCallback(async () => {
    if (!file || !wallet || !userAddress) return
    reset()

    try {
      // 1. Read PDF as base64
      const pdfBase64 = await fileToBase64(file)

      // 2. Pay via Privy-signed ERC-20 transfer
      setStage('paying')
      const provider = await wallet.getEthereumProvider()
      const walletClient = createWalletClient({
        account: userAddress,
        chain: tempoTestnet,
        transport: custom(provider),
      })
      const hash = await walletClient.writeContract({
        address: USDC_ADDRESS,
        abi: ERC20_ABI,
        functionName: 'transfer',
        args: [TREASURY_ADDRESS, parseUnits(PRICE_USDC, USDC_DECIMALS)],
      })
      setTxHash(hash)

      // 3. Wait for on-chain confirmation (Tempo finalizes in ~0.6s)
      setStage('waiting')
      const publicClient = createPublicClient({ chain: tempoTestnet, transport: http() })
      await publicClient.waitForTransactionReceipt({ hash })

      // 4. POST to backend, stream SSE response
      setStage('analyzing')
      const res = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          tx_hash: hash,
          pdf_base64: pdfBase64,
          title: file.name,
        }),
      })
      if (!res.ok || !res.body) {
        const text = await res.text().catch(() => '')
        throw new Error(`HTTP ${res.status}: ${text || res.statusText}`)
      }

      for await (const ev of parseSse(res.body)) {
        switch (ev.type) {
          case 'run':
            setRunId(ev.data.run_id)
            break
          case 'text':
            setAnalysis((prev) => prev + ev.data)
            break
          case 'tool_use':
            setToolCalls((prev) => [...prev, { name: ev.data.name }])
            break
          case 'done':
            setTokens({ input: ev.data.input_tokens, output: ev.data.output_tokens })
            break
          case 'error':
            throw new Error(ev.data)
        }
      }
      setStage('done')
    } catch (e: any) {
      setStage('error')
      setError(e?.shortMessage || e?.message || String(e))
    }
  }, [file, wallet, userAddress])

  if (!ready) return <Shell>Loading…</Shell>

  return (
    <Shell>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">Financing offer analyzer</h1>
          <p className="text-sm text-gray-600 mt-1">
            Upload a PDF financing offer, pay {PRICE_USDC} testUSDC, get a plain-English analysis.
          </p>
        </div>
        {authenticated && (
          <button className="text-xs underline text-gray-500" onClick={() => logout()}>
            Log out
          </button>
        )}
      </div>

      {!configured && (
        <Banner tone="amber">
          Config missing — copy <code>.env.local.example</code> to <code>.env.local</code>.
        </Banner>
      )}

      {!authenticated ? (
        <button className="px-4 py-2 rounded bg-black text-white" onClick={() => login()}>
          Log in to get started
        </button>
      ) : (
        <div className="space-y-6">
          <section className="p-4 rounded border bg-white">
            <div className="text-xs text-gray-500 mb-2">Your wallet</div>
            <div className="font-mono text-xs break-all">{userAddress || 'provisioning…'}</div>
          </section>

          <section className="p-4 rounded border bg-white space-y-3">
            <h2 className="font-medium">1. Upload PDF</h2>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
            {file && (
              <div className="text-sm text-gray-600">
                {file.name} — {(file.size / 1024).toFixed(1)} KB
              </div>
            )}
          </section>

          <section className="p-4 rounded border bg-white space-y-3">
            <h2 className="font-medium">2. Pay & analyze</h2>
            <button
              className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-50"
              disabled={analyzeDisabled}
              onClick={handleAnalyze}
            >
              {stage === 'paying' && 'Signing payment…'}
              {stage === 'waiting' && 'Waiting for confirmation…'}
              {stage === 'analyzing' && 'Analyzing…'}
              {(stage === 'idle' || stage === 'done' || stage === 'error') &&
                `Analyze for ${PRICE_USDC} testUSDC`}
            </button>
            {txHash && (
              <div className="text-xs font-mono break-all text-gray-600">
                tx: {txHash}
              </div>
            )}
            {runId && (
              <div className="text-xs text-gray-600">run: {runId}</div>
            )}
            {error && <Banner tone="red">{error}</Banner>}
          </section>

          {(analysis || toolCalls.length > 0) && (
            <section className="p-4 rounded border bg-white space-y-3">
              <h2 className="font-medium">Analysis</h2>
              {toolCalls.length > 0 && (
                <div className="text-xs text-gray-500">
                  tools: {toolCalls.map((t) => t.name).join(', ')}
                </div>
              )}
              <pre className="whitespace-pre-wrap text-sm leading-relaxed font-sans">
                {analysis}
                {stage === 'analyzing' && <span className="animate-pulse">▍</span>}
              </pre>
              {tokens && (
                <div className="text-xs text-gray-400">
                  {tokens.input} input tokens / {tokens.output} output tokens
                </div>
              )}
            </section>
          )}

          <div className="text-xs text-gray-400">
            Debug tool at <a href="/debug" className="underline">/debug</a>.
          </div>
        </div>
      )}
    </Shell>
  )
}

async function fileToBase64(file: File): Promise<string> {
  const buf = await file.arrayBuffer()
  // Avoid call-stack overflow on large files
  let binary = ''
  const bytes = new Uint8Array(buf)
  const chunk = 0x8000
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
  }
  return btoa(binary)
}

async function* parseSse(body: ReadableStream<Uint8Array>): AsyncIterable<StreamEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // Split on blank-line boundary between events
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const event = parseFrame(frame)
      if (event) yield event
    }
  }
}

function parseFrame(frame: string): StreamEvent | null {
  let eventName = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) eventName = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return null
  const raw = dataLines.join('\n')
  try {
    const data = JSON.parse(raw)
    return { type: eventName, data } as StreamEvent
  } catch {
    return { type: eventName, data: raw } as StreamEvent
  }
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="max-w-2xl mx-auto p-6">
      <div className="mt-8">{children}</div>
    </main>
  )
}

function Banner({
  children,
  tone,
}: {
  children: React.ReactNode
  tone: 'amber' | 'red'
}) {
  const palette =
    tone === 'amber'
      ? 'border-amber-300 bg-amber-50 text-amber-900'
      : 'border-red-300 bg-red-50 text-red-900'
  return <div className={`p-3 rounded border text-sm ${palette}`}>{children}</div>
}
