import { defineChain } from "viem";

export const GENLAYER_CHAIN_ID = Number(import.meta.env.VITE_CHAIN_ID ?? 61999);
export const GENLAYER_RPC_URL =
  import.meta.env.VITE_RPC_URL ?? "https://studio.genlayer.com/api";
export const GENLAYER_EXPLORER_URL =
  import.meta.env.VITE_EXPLORER_URL ?? "https://explorer-studio.genlayer.com";

export const CONTRACT_ADDRESS = (import.meta.env.VITE_CONTRACT_ADDRESS ??
  "0xcFf77B51300884ad03c94601b60211Bc47B2aD25") as `0x${string}`;

export const GENLAYER_NETWORK = "studionet" as const;

export const genLayerStudioNet = defineChain({
  id: GENLAYER_CHAIN_ID,
  name: "GenLayer StudioNet",
  nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
  rpcUrls: {
    default: { http: [GENLAYER_RPC_URL] },
    public: { http: [GENLAYER_RPC_URL] },
  },
  blockExplorers: {
    default: { name: "GenLayer Explorer", url: GENLAYER_EXPLORER_URL },
  },
  testnet: true,
});
