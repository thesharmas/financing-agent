# Financing Agent — Phase 1 Frontend

A throwaway learning spike: log in via Privy, get a Tempo testnet wallet, send test USDC to a treasury address, verify the transaction server-side.

## Setup

1. `cp .env.local.example .env.local` — Tempo Moderato testnet values are pre-filled; only `NEXT_PUBLIC_TREASURY_ADDRESS` is missing.
2. `nvm use 20` (Next.js 14 requires Node ≥ 18.17)
3. `npm install`
4. `npm run dev`, open http://localhost:3000, log in with Google/email
5. Once logged in, log out and log in with a *second* email to create a throwaway treasury wallet. Copy that address into `.env.local` as `NEXT_PUBLIC_TREASURY_ADDRESS`.
6. Log back in as your primary user.

## Getting test tokens

Visit [Tempo's faucet](https://docs.tempo.xyz/quickstart/faucet), paste your wallet address from the app, receive 1,000,000 test stablecoins (pathUSD by default). Refresh the app to see the balance.

## Network

- Chain: Tempo Testnet (Moderato), chain ID `42431`
- RPC: `https://rpc.moderato.tempo.xyz`
- Explorer: `https://explore.testnet.tempo.xyz`
- Default stablecoin: pathUSD `0x20c0000000000000000000000000000000000000`

## What this proves

- Privy login + auto-provisioned embedded wallet
- Reading an ERC-20 balance via RPC (`balanceOf`)
- Signing an ERC-20 `transfer` call via the embedded wallet
- Server-side tx verification by fetching a receipt and decoding the Transfer event

## What's deliberately missing

- No idempotency (same tx hash can be "verified" twice)
- No user database or balance ledger
- No PDF upload, no agent run
- No mainnet, no card on-ramp

All of that arrives in phase 2.
