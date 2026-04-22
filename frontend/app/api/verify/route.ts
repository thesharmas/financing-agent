import { NextResponse } from 'next/server'
import {
  createPublicClient,
  decodeEventLog,
  formatUnits,
  http,
  type Hash,
} from 'viem'
import { tempoTestnet } from '@/lib/chain'
import { ERC20_ABI, USDC_ADDRESS, USDC_DECIMALS } from '@/lib/usdc'

export async function POST(req: Request) {
  const { tx_hash } = (await req.json()) as { tx_hash?: string }

  if (!tx_hash || !tx_hash.startsWith('0x')) {
    return NextResponse.json({ ok: false, error: 'missing or malformed tx_hash' }, { status: 400 })
  }

  try {
    const client = createPublicClient({ chain: tempoTestnet, transport: http() })
    const receipt = await client.getTransactionReceipt({ hash: tx_hash as Hash })

    const transferLog = receipt.logs.find(
      (log) => log.address.toLowerCase() === USDC_ADDRESS.toLowerCase(),
    )

    if (!transferLog) {
      return NextResponse.json({
        ok: false,
        error: 'no USDC Transfer log in this tx',
        status: receipt.status,
        blockNumber: receipt.blockNumber.toString(),
      })
    }

    const decoded = decodeEventLog({
      abi: ERC20_ABI,
      data: transferLog.data,
      topics: transferLog.topics,
    })

    if (decoded.eventName !== 'Transfer') {
      return NextResponse.json({ ok: false, error: `unexpected event ${decoded.eventName}` })
    }

    const { from, to, value } = decoded.args as { from: string; to: string; value: bigint }

    return NextResponse.json({
      ok: receipt.status === 'success',
      from,
      to,
      amount: formatUnits(value, USDC_DECIMALS),
      status: receipt.status,
      blockNumber: receipt.blockNumber.toString(),
    })
  } catch (e: any) {
    return NextResponse.json(
      { ok: false, error: e?.shortMessage || e?.message || String(e) },
      { status: 500 },
    )
  }
}
