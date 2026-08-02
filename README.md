- **App**: https://salamy99.github.io/credential-check/

# Attest — credential-check

Credential / diploma verification on GenLayer. A holder submits a credential, but the matching official registry record can only be bound by the deployment-time registry authority. This prevents a holder or random wallet from attaching matching fabricated registry text.

## How it works

1. **`submit_credential`** — the holder submits the institution and credential text.
2. **`attach_registry`** — registry-authority-only binding of the official registry record.
3. **`run_field_extraction`** — GenLayer validators extract the five identity-critical fields from both sides: holder name, institution, program, issue date, registry id.
4. **`run_cross_check`** — validators judge each field as concordant or conflicting, then compute match count, contradiction flag, verdict, and badge tier.
5. **`issue_badge`** — only a VERIFIED credential can mint a badge reference.
6. **`revoke_badge`** — the holder can revoke a badge.

## On-chain

- **Contract:** `0xcFf77B51300884ad03c94601b60211Bc47B2aD25`
- **Network:** GenLayer StudioNet (chain id 61999)
- **Explorer:** https://explorer-studio.genlayer.com/address/0xcFf77B51300884ad03c94601b60211Bc47B2aD25

## Run locally

```bash
cd frontend
npm install
npm run dev
```

## Tech stack

- GenLayer Python intelligent contract (`backend/`)
- React 18 + TypeScript + Vite (`frontend/`)
- wagmi · RainbowKit · genlayer-js · viem
