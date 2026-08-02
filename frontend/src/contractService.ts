import { createClient, createAccount } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { TransactionStatus, CalldataAddress } from "genlayer-js/types";
import { hexToBytes } from "viem";
import { CONTRACT_ADDRESS, GENLAYER_NETWORK } from "./chain";

type Hex = `0x${string}`;
const ADDR = CONTRACT_ADDRESS as Hex;
const TIMEOUT_MS = 300_000;

export type Verdict = "UNKNOWN" | "INVALID" | "PENDING" | "VERIFIED" | "";
export type State =
  | "DRAFT" | "AWAITING_REGISTRY" | "REGISTRY_BOUND" | "EXTRACTING" | "CROSS_CHECKING" | "RULED" | "BADGED" | "REVOKED" | "";
export type Tier = "NONE" | "BRONZE" | "SILVER" | "GOLD" | "";

const VERDICT_NAMES: Verdict[] = ["UNKNOWN", "INVALID", "PENDING", "VERIFIED"];
const STATE_NAMES: State[] = ["DRAFT", "AWAITING_REGISTRY", "REGISTRY_BOUND", "EXTRACTING", "CROSS_CHECKING", "RULED", "BADGED", "REVOKED"];
const TIER_NAMES: Tier[] = ["NONE", "BRONZE", "SILVER", "GOLD"];

export interface CredRow {
  id: number;
  institution: string;
  state: State;
  verdict: Verdict;
  tier: Tier;
  matches: number;
}
export interface CredDetail {
  id: number;
  holder: string;
  institution: string;
  submittedText: string;
  registryText: string;
  state: State;
  verdict: Verdict;
  tier: Tier;
  matches: number;
  contradiction: boolean;
  badgeRef: string;
  rationale: string;
  registryAttestor: string;
  registryBindingHash: string;
  registrySourceType: string;
}
export interface FieldVerdictView {
  field: string;
  submitted: string;
  registry: string;
  concord: boolean;
  conflicts: boolean;
  confidence: number;
  note: string;
}
export interface Counts {
  submitted: number;
  ruled: number;
  verified: number;
  invalid: number;
  badged: number;
  revoked: number;
  next: number;
  registryAuthority: string;
}

let _read: ReturnType<typeof createClient> | null = null;
function readClient() {
  if (!_read) _read = createClient({ chain: studionet, account: createAccount() });
  return _read;
}
async function writeClient(account: Hex) {
  const c = createClient({ chain: studionet, account });
  await c.connect(GENLAYER_NETWORK);
  return c;
}

async function send(account: Hex, functionName: string, args: any[]): Promise<string> {
  const client = await writeClient(account);
  const hash = await client.writeContract({ address: ADDR, functionName, args, value: 0n });
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error("Timed out waiting for consensus")), TIMEOUT_MS);
  });
  try {
    await Promise.race([
      client.waitForTransactionReceipt({ hash, status: TransactionStatus.ACCEPTED, interval: 5000, retries: 110 }),
      timeout,
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
  return String(hash);
}

function num(v: unknown): number {
  if (v === undefined || v === null) return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}
function str(v: unknown): string {
  return v === undefined || v === null ? "" : String(v);
}
function bool(v: unknown): boolean {
  return v === true || v === "true" || v === 1 || v === "1";
}
function pick(o: any, k: string, i: number): any {
  if (o == null) return undefined;
  if (Array.isArray(o)) return o[i];
  if (typeof o === "object" && k in o) return o[k];
  return undefined;
}
function addrArg(a: string) {
  return new CalldataAddress(hexToBytes(a as Hex));
}

// ---- writes (all non-payable) ----
export async function submitCredential(account: Hex, institution: string, text: string): Promise<number> {
  await send(account, "submit_credential", [institution.trim(), text.trim()]);
  for (let i = 0; i < 6; i++) {
    try {
      const c = await getCounts();
      if (c.next > 0) return c.next - 1;
    } catch {
      /* lag */
    }
    await new Promise((r) => setTimeout(r, 2500));
  }
  return -1;
}
export async function attachRegistry(account: Hex, id: number, registry: string): Promise<void> {
  await send(account, "attach_registry", [id, registry.trim()]);
}
export async function runFieldExtraction(account: Hex, id: number): Promise<void> {
  await send(account, "run_field_extraction", [id]);
}
export async function runCrossCheck(account: Hex, id: number): Promise<void> {
  await send(account, "run_cross_check", [id]);
}
export async function issueBadge(account: Hex, id: number): Promise<void> {
  await send(account, "issue_badge", [id]);
}
export async function revokeBadge(account: Hex, id: number, reason: string): Promise<void> {
  await send(account, "revoke_badge", [id, reason.trim() || "revoked"]);
}

// ---- reads ----
export async function getCounts(): Promise<Counts> {
  const r: any = await readClient().readContract({ address: ADDR, functionName: "get_counts", args: [] });
  return {
    submitted: num(pick(r, "submitted_total", 0)),
    ruled: num(pick(r, "ruled_total", 1)),
    verified: num(pick(r, "verified_total", 2)),
    invalid: num(pick(r, "invalid_total", 3)),
    badged: num(pick(r, "badged_total", 4)),
    revoked: num(pick(r, "revoked_total", 5)),
    next: num(pick(r, "next_credential_id", 6)),
    registryAuthority: str(pick(r, "registry_authority", 8)),
  };
}

export async function listHolder(holder: Hex): Promise<CredRow[]> {
  const r: any = await readClient().readContract({
    address: ADDR,
    functionName: "get_holder_credentials",
    args: [addrArg(holder)],
  });
  if (!Array.isArray(r)) return [];
  return r.map((c: any) => ({
    id: num(pick(c, "credential_id", 0)),
    institution: str(pick(c, "institution", 1)),
    state: (str(pick(c, "state", 2)) || "") as State,
    verdict: (str(pick(c, "verdict", 3)) || "") as Verdict,
    tier: (str(pick(c, "tier", 4)) || "NONE") as Tier,
    matches: num(pick(c, "matches", 5)),
  }));
}

export async function getCredential(id: number): Promise<CredDetail> {
  const r: any = await readClient().readContract({ address: ADDR, functionName: "get_credential", args: [id] });
  const stateNum = Number(pick(r, "state", 7) ?? 0);
  const verdictNum = Number(pick(r, "verdict", 11) ?? 0);
  const tierNum = Number(pick(r, "tier", 12) ?? 0);
  return {
    id,
    holder: str(pick(r, "holder", 0)),
    institution: str(pick(r, "institution", 1)),
    submittedText: str(pick(r, "submitted_text", 3)),
    registryText: str(pick(r, "registry_text", 5)),
    state: (STATE_NAMES[stateNum] || "") as State,
    verdict: (VERDICT_NAMES[verdictNum] || "") as Verdict,
    tier: (TIER_NAMES[tierNum] || "NONE") as Tier,
    matches: num(pick(r, "registry_matches", 9)),
    contradiction: bool(pick(r, "contradiction", 10)),
    badgeRef: str(pick(r, "badge_ref", 13)),
    rationale: str(pick(r, "rationale", 14)),
    registryAttestor: str(pick(r, "registry_attestor", 19)),
    registryBindingHash: str(pick(r, "registry_binding_hash", 20)),
    registrySourceType: str(pick(r, "registry_source_type", 21)),
  };
}

export async function getFieldVerdicts(id: number): Promise<FieldVerdictView[]> {
  try {
    const r: any = await readClient().readContract({ address: ADDR, functionName: "get_field_verdicts", args: [id] });
    if (!Array.isArray(r)) return [];
    return r.map((f: any) => ({
      field: str(pick(f, "field", 0)),
      submitted: str(pick(f, "submitted", 1)),
      registry: str(pick(f, "registry", 2)),
      concord: bool(pick(f, "concord", 3)),
      conflicts: bool(pick(f, "conflicts", 4)),
      confidence: num(pick(f, "confidence", 5)),
      note: str(pick(f, "note", 6)),
    }));
  } catch {
    return [];
  }
}

export { VERDICT_NAMES, STATE_NAMES, TIER_NAMES };
