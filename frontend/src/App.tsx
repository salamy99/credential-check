import { useEffect, useState } from "react";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useAccount } from "wagmi";
import {
  submitCredential,
  attachRegistry,
  runFieldExtraction,
  runCrossCheck,
  issueBadge,
  revokeBadge,
  getCounts,
  listHolder,
  getCredential,
  getFieldVerdicts,
  CredRow,
  CredDetail,
  FieldVerdictView,
  Counts,
} from "./contractService";
import { CONTRACT_ADDRESS } from "./chain";

type Hex = `0x${string}`;
function shortAddr(a: string): string {
  return a && a.length > 12 ? `${a.slice(0, 6)}...${a.slice(-4)}` : a || "-";
}

function BootLines() {
  const lines = ["[BOOT] kernel up", "[BOOT] loading registry...", "[BOOT] verifier online", "[NET] studionet :: STATUS=LIVE"];
  const [n, setN] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setN((p) => Math.min(lines.length, p + 1)), 380);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="boot">
      {lines.slice(0, n).map((l, i) => (
        <div key={i} className="boot-l">{l}</div>
      ))}
      {n >= lines.length && <div className="boot-l">guest@attest:~$ <i className="cur">█</i></div>}
    </div>
  );
}

export function App() {
  const { address, isConnected } = useAccount();
  const acct = address as Hex | undefined;
  const [showSubmit, setShowSubmit] = useState(false);
  const [institution, setInstitution] = useState("");
  const [text, setText] = useState("");
  const [registry, setRegistry] = useState("");
  const [reason, setReason] = useState("");

  const [rows, setRows] = useState<CredRow[]>([]);
  const [counts, setCounts] = useState<Counts>({ submitted: 0, ruled: 0, verified: 0, invalid: 0, badged: 0, revoked: 0, next: 0, registryAuthority: "" });
  const [selId, setSelId] = useState<number | null>(null);
  const [sel, setSel] = useState<CredDetail | null>(null);
  const [fields, setFields] = useState<FieldVerdictView[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [netErr, setNetErr] = useState(false);

  async function loadSel(id: number) {
    const c = await getCredential(id);
    setSel(c);
    setFields(await getFieldVerdicts(id));
  }

  async function refreshAll() {
    if (typeof document !== "undefined" && document.hidden) return;
    try {
      setCounts(await getCounts());
      if (acct) setRows(await listHolder(acct));
      else setRows([]);
      if (selId != null) {
        try {
          await loadSel(selId);
        } catch {
          /* keep */
        }
      }
      setNetErr(false);
    } catch {
      setNetErr(true);
    }
  }
  useEffect(() => {
    refreshAll();
    const t = setInterval(refreshAll, 12000);
    const onVis = () => {
      if (!document.hidden) refreshAll();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", onVis);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [acct, selId]);

  async function copyText(t: string) {
    try {
      await navigator.clipboard.writeText(t);
    } catch {
      /* clipboard blocked */
    }
  }
  async function pick(id: number) {
    setSelId(id);
    try {
      await loadSel(id);
    } catch {
      setSel(null);
      setFields([]);
    }
  }
  async function run<T>(label: string, fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(label);
    setNote("");
    try {
      return await fn();
    } catch (e) {
      setNote(String((e as Error).message || e).slice(0, 220));
      return undefined;
    } finally {
      setBusy(null);
      refreshAll();
    }
  }
  async function onSubmit() {
    if (!acct) return;
    if (institution.trim().length < 2) return setNote("--institution required");
    if (text.trim().length < 30) return setNote("--credential_text >=30 chars");
    const id = await run("$ submit_credential", () => submitCredential(acct, institution, text));
    if (id != null && id >= 0) {
      setInstitution("");
      setText("");
      setShowSubmit(false);
      pick(id);
    }
  }
  async function onAttach() {
    if (!acct || selId == null) return;
    if (registry.trim().length < 30) return setNote("--registry_text >=30 chars");
    await run("$ attach_registry", () => attachRegistry(acct, selId, registry));
    setRegistry("");
  }
  async function onExtract() {
    if (!acct || selId == null) return;
    await run("$ run_field_extraction", () => runFieldExtraction(acct, selId));
  }
  async function onCross() {
    if (!acct || selId == null) return;
    await run("$ run_cross_check", () => runCrossCheck(acct, selId));
  }
  async function onBadge() {
    if (!acct || selId == null) return;
    await run("$ issue_badge", () => issueBadge(acct, selId));
  }
  async function onRevoke() {
    if (!acct || selId == null) return;
    await run("$ revoke_badge", () => revokeBadge(acct, selId, reason));
    setReason("");
  }

  return (
    <div className="app-root">
      <BootLines />
      <header className="topbar">
        <span className="wm">Attest</span>
        <span className="claim">attest :: credential verification</span>
        <span className="net-line">[NET] studionet :: STATUS={netErr ? "RECONNECTING" : "LIVE"}</span>
        <ConnectButton showBalance={false} chainStatus="none" accountStatus="address" />
      </header>

      <section className="readouts">
        <div className="ro"><span className="k">credentials</span><span className="v">{counts.next}</span></div>
        <div className="ro"><span className="k">ruled</span><span className="v">{counts.ruled}</span></div>
        <div className="ro"><span className="k">verified</span><span className="v">{counts.verified}</span></div>
        <div className="ro">
          <span className="k">contract</span>
          <button type="button" className="copybtn" aria-label="Copy contract address" onClick={() => copyText(CONTRACT_ADDRESS)}>
            <code className="v">{shortAddr(CONTRACT_ADDRESS)}</code> ⧉
          </button>
        </div>
      </section>

      <p className="prov">
        Source: the official registry / diploma record bound by the registry authority, judged by GenLayer validators via{" "}
        <code>gl.nondet.exec_prompt</code>, with the ruling reached by consensus.
      </p>

      <section className="actions-row">
        <button className="btn-grn" disabled={!isConnected} onClick={() => setShowSubmit(!showSubmit)}>
          {showSubmit ? "[ CLOSE ]" : "[ NEW CREDENTIAL ]"}
        </button>
      </section>
      {showSubmit && (
        <section className="cmd">
          <div className="cmd-l">$ submit_credential --institution &lt;str&gt; --credential_text &lt;str&gt;</div>
          <label>--institution</label>
          <input value={institution} onChange={(e) => setInstitution(e.target.value)} />
          <label>--credential_text</label>
          <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Diploma / certificate text — holder name, institution, program, issue date, registry id." />
          <button className="btn-grn" disabled={!isConnected || !!busy} onClick={onSubmit}>
            [ ENTER ]
          </button>
        </section>
      )}

      <section className="log">
        <div className="log-cap">// your credentials</div>
        {!isConnected ? (
          <div className="log-l">// connect wallet to view your credentials</div>
        ) : rows.length === 0 ? (
          <div className="log-l">// empty</div>
        ) : (
          rows.map((r) => (
            <div
              key={r.id}
              className={`log-l v-${r.verdict || "pending"} ${selId === r.id ? "sel" : ""}`}
              onClick={() => pick(r.id)}
              tabIndex={0}
              role="button"
              aria-label={`Credential ${r.id}, ${r.institution}, ${r.verdict || "pending"}`}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  pick(r.id);
                }
              }}
            >
              [CRED #{String(r.id).padStart(4, "0")}] STATE={r.state} VERDICT=
              <span className={`v-${r.verdict || "pending"}`}>{r.verdict || "PENDING"}</span> TIER={r.tier} MATCHES={r.matches}/5 INST=
              <code>{r.institution}</code>
            </div>
          ))
        )}
      </section>

      {sel && selId != null && (
        <section className="cmd sel-panel">
          <div className="cmd-l">$ describe CRED #{String(selId).padStart(4, "0")}</div>
          <div className="kv-l">
            VERDICT = <span className={`v-${sel.verdict || "pending"}`}>{sel.verdict || "PENDING"}</span> · TIER = {sel.tier} · MATCHES = {sel.matches}/5 · CONTRA = {sel.contradiction ? "1" : "0"} · STATE = {sel.state}
            {sel.badgeRef ? <> · BADGE = {sel.badgeRef}</> : null}
          </div>

          {sel.submittedText && (
            <div className="ev-block">
              <div className="ev-h">// credential</div>
              <div className="ev">{sel.submittedText}</div>
            </div>
          )}
          {sel.registryText && (
            <div className="ev-block">
              <div className="ev-h">// registry</div>
              <div className="ev reg">{sel.registryText}</div>
            </div>
          )}
          {fields.length > 0 && (
            <div className="ev-block">
              <div className="ev-h">// field-by-field</div>
              {fields.map((f) => (
                <div key={f.field} className="fv-l">
                  {f.field.padEnd(14, " ")} {f.concord ? "AGREE" : f.conflicts ? "CONFLICT" : "—"} conf={f.confidence}
                  {f.note ? ` :: ${f.note}` : ""}
                </div>
              ))}
            </div>
          )}
          {sel.rationale && (
            <div className="ev-block">
              <div className="ev-h">// rationale</div>
              <div className="ev rat">{sel.rationale}</div>
            </div>
          )}

          {sel.state === "AWAITING_REGISTRY" && (
            <>
              <label>--registry_text</label>
              <textarea value={registry} onChange={(e) => setRegistry(e.target.value)} placeholder="Official registry record / verification text." />
              <button className="btn-grn" disabled={!isConnected || !!busy} onClick={onAttach}>
                [ RUN attach_registry ]
              </button>
            </>
          )}
          {sel.state === "REGISTRY_BOUND" && (
            <button className="btn-grn" disabled={!isConnected || !!busy} onClick={onExtract}>
              [ RUN run_field_extraction ]
            </button>
          )}
          {sel.state === "EXTRACTING" && (
            <button className="btn-grn" disabled={!isConnected || !!busy} onClick={onCross}>
              [ RUN run_cross_check ]
            </button>
          )}
          {sel.state === "RULED" && sel.verdict === "VERIFIED" && (
            <button className="btn-grn" disabled={!isConnected || !!busy} onClick={onBadge}>
              [ RUN issue_badge ]
            </button>
          )}
          {sel.state === "RULED" && sel.verdict !== "VERIFIED" && <p className="dim">// no badge — verdict {sel.verdict}</p>}
          {sel.state === "BADGED" && (
            <>
              <p className="dim">// badged.</p>
              <label>--reason</label>
              <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="revocation reason" />
              <button className="btn-grn" disabled={!isConnected || !!busy} onClick={onRevoke}>
                [ RUN revoke_badge ]
              </button>
            </>
          )}
          {sel.state === "REVOKED" && <p className="dim">// revoked.</p>}
        </section>
      )}

      {(busy || note) && <div className="toast">{busy ? `${busy}_` : note}</div>}
    </div>
  );
}
