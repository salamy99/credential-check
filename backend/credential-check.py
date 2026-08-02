# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
import hashlib
from dataclasses import dataclass
from enum import IntEnum
from genlayer import *


class State(IntEnum):
    DRAFT = 0
    AWAITING_REGISTRY = 1
    REGISTRY_BOUND = 2
    EXTRACTING = 3
    CROSS_CHECKING = 4
    RULED = 5
    BADGED = 6
    REVOKED = 7


class Action(IntEnum):
    BIND_REGISTRY = 1
    BEGIN_EXTRACT = 2
    SETTLE_EXTRACT = 3
    BEGIN_CROSSCHECK = 4
    SETTLE_RULING = 5
    ISSUE_BADGE = 6
    REVOKE = 7


class Verdict(IntEnum):
    UNKNOWN = 0
    INVALID = 1
    PENDING = 2
    VERIFIED = 3


class BadgeTier(IntEnum):
    NONE = 0
    BRONZE = 1
    SILVER = 2
    GOLD = 3


VERDICT_NAMES = {
    int(Verdict.UNKNOWN): "UNKNOWN",
    int(Verdict.INVALID): "INVALID",
    int(Verdict.PENDING): "PENDING",
    int(Verdict.VERIFIED): "VERIFIED",
}

TIER_NAMES = {
    int(BadgeTier.NONE): "NONE",
    int(BadgeTier.BRONZE): "BRONZE",
    int(BadgeTier.SILVER): "SILVER",
    int(BadgeTier.GOLD): "GOLD",
}

STATE_NAMES = {
    int(State.DRAFT): "DRAFT",
    int(State.AWAITING_REGISTRY): "AWAITING_REGISTRY",
    int(State.REGISTRY_BOUND): "REGISTRY_BOUND",
    int(State.EXTRACTING): "EXTRACTING",
    int(State.CROSS_CHECKING): "CROSS_CHECKING",
    int(State.RULED): "RULED",
    int(State.BADGED): "BADGED",
    int(State.REVOKED): "REVOKED",
}


E_BAD_INSTITUTION = 1001
E_BAD_CRED_TEXT = 1002
E_BAD_REGISTRY_TEXT = 1003
E_UNKNOWN_CREDENTIAL = 1004
E_WRONG_STATE = 1005
E_NOT_HOLDER = 1006
E_NOT_VERIFIED = 1007
E_ALREADY_BADGED = 1008
E_BAD_OFFSET = 1009
E_INVALID_TRANSITION = 1010
E_INSTITUTION_TOO_LONG = 1011
E_DOSSIER_TOO_LONG = 1012
E_INVALID_VERDICT_BAND = 1013
E_NOT_REGISTRY_AUTHORITY = 1014

E_LLM_NOT_DICT = 2001
E_LLM_MISSING_FIELD = 2002
E_LLM_BAD_INT = 2003
E_LLM_OUT_OF_RANGE = 2004
E_LLM_BAD_BOOL = 2005
E_LLM_VALIDATOR_REJECT = 2006

E_NET_4XX = 3001
E_NET_5XX = 3002
E_NET_BODY = 3003

E_TRANS_FAULT = 4001


_TAG_EXPECTED = "exp.cred."
_TAG_LLM = "llm.cred."
_TAG_NET = "net.cred."
_TAG_TRANS = "tmp.cred."


KEY_FIELD_NAMES = (
    "holder_name",
    "institution",
    "program_title",
    "issue_date",
    "registry_id",
)
KEY_FIELD_COUNT = len(KEY_FIELD_NAMES)

BADGE_GOLD_MIN = 5
BADGE_SILVER_MIN = 4
BADGE_BRONZE_MIN = 3
VERIFIED_MIN_MATCHES = 3
PENDING_MIN_MATCHES = 1

MATCH_VALIDATOR_TOL = 1
PER_FIELD_VOTE_TOL = 0
INSTITUTION_MAX_LEN = 160
CRED_TEXT_MIN_LEN = 30
CRED_TEXT_MAX_LEN = 6000
REGISTRY_TEXT_MIN_LEN = 30
REGISTRY_TEXT_MAX_LEN = 6000


def _bail_expected(code: int, **detail) -> None:
    payload = json.dumps(detail, sort_keys=True, ensure_ascii=False, default=str)
    raise gl.vm.UserError(f"{_TAG_EXPECTED}E{code:04d} {payload}")


def _bail_llm(code: int, **detail) -> None:
    payload = json.dumps(detail, sort_keys=True, ensure_ascii=False, default=str)
    raise gl.vm.UserError(f"{_TAG_LLM}E{code:04d} {payload}")


def _bail_net(code: int, **detail) -> None:
    payload = json.dumps(detail, sort_keys=True, ensure_ascii=False, default=str)
    raise gl.vm.UserError(f"{_TAG_NET}E{code:04d} {payload}")


def _bail_trans(code: int, **detail) -> None:
    payload = json.dumps(detail, sort_keys=True, ensure_ascii=False, default=str)
    raise gl.vm.UserError(f"{_TAG_TRANS}E{code:04d} {payload}")


def _fault_tag(msg: str) -> str:
    if not msg:
        return ""
    for tag in (_TAG_EXPECTED, _TAG_LLM, _TAG_NET, _TAG_TRANS):
        if msg.startswith(tag):
            return tag
    return ""


def _consensus_on_fault(leaders_res, run_fn) -> bool:
    leader_msg = leaders_res.message if hasattr(leaders_res, "message") else ""
    try:
        run_fn()
        return False
    except gl.vm.UserError as e:
        local_msg = e.message if hasattr(e, "message") else str(e)
        leader_tag = _fault_tag(leader_msg)
        local_tag = _fault_tag(local_msg)
        if not leader_tag or leader_tag != local_tag:
            return False
        if leader_tag == _TAG_EXPECTED:
            return local_msg == leader_msg
        return True


def _coerce_int(x, default=None):
    try:
        return int(float(str(x).strip()))
    except Exception:
        return default


def _coerce_bool(x):
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    if s in ("true", "1", "yes", "y", "t"):
        return True
    if s in ("false", "0", "no", "n", "f"):
        return False
    return None


def _clamp(n: int, lo: int, hi: int) -> int:
    if n < lo:
        return lo
    if n > hi:
        return hi
    return n


def _trim(s: str, n: int) -> str:
    try:
        ss = str(s)
    except Exception:
        return ""
    return ss[:n]


def _hash20(s: str) -> str:
    try:
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:40]
    except Exception:
        return "0" * 40


def _hex_address(addr: Address) -> str:
    try:
        return "0x" + bytes(addr.as_bytes).hex()
    except Exception:
        try:
            return "0x" + bytes(addr).hex()
        except Exception:
            return "0x"


def _as_address(value) -> Address:
    if isinstance(value, Address):
        return value
    if isinstance(value, (bytes, bytearray)):
        return Address(bytes(value))
    if hasattr(value, "as_bytes"):
        return Address(value.as_bytes)
    return Address(value)


def _verdict_from_matches(matches: int, contradiction: bool) -> Verdict:
    if contradiction:
        return Verdict.INVALID
    if matches >= VERIFIED_MIN_MATCHES:
        return Verdict.VERIFIED
    if matches >= PENDING_MIN_MATCHES:
        return Verdict.PENDING
    return Verdict.INVALID


def _tier_from_matches(matches: int, contradiction: bool) -> BadgeTier:
    if contradiction:
        return BadgeTier.NONE
    if matches >= BADGE_GOLD_MIN:
        return BadgeTier.GOLD
    if matches >= BADGE_SILVER_MIN:
        return BadgeTier.SILVER
    if matches >= BADGE_BRONZE_MIN:
        return BadgeTier.BRONZE
    return BadgeTier.NONE


@allow_storage
@dataclass
class FieldVerdict:
    field_name: str
    submitted_excerpt: str
    registry_excerpt: str
    concord: bool
    conflicts: bool
    confidence: u8
    note: str


@allow_storage
@dataclass
class Credential:
    holder: Address
    institution: str
    institution_hash: str
    submitted_text: str
    submitted_hash: str
    registry_text: str
    registry_hash: str
    state: u8
    state_history_summary: str
    registry_matches: u32
    contradiction: bool
    verdict: u8
    tier: u8
    badge_ref: str
    rationale: str
    submitted_at_seq: u64
    last_transition_seq: u64
    badged_at_seq: u64
    revoked_at_seq: u64
    registry_attestor: str
    registry_binding_hash: str
    registry_source_type: str


@allow_storage
@dataclass
class TransitionLog:
    seq: u64
    credential_id: u32
    actor: Address
    from_state: u8
    action: u8
    to_state: u8
    detail: str


@allow_storage
@dataclass
class InstitutionRoll:
    institution: str
    institution_hash: str
    total: u32
    verified: u32
    invalid: u32
    badged: u32
    last_credential_id: u32


def _state_label(s: int) -> str:
    return STATE_NAMES.get(int(s), f"S({int(s)})")


def _action_label(a: int) -> str:
    return {
        int(Action.BIND_REGISTRY): "BIND_REGISTRY",
        int(Action.BEGIN_EXTRACT): "BEGIN_EXTRACT",
        int(Action.SETTLE_EXTRACT): "SETTLE_EXTRACT",
        int(Action.BEGIN_CROSSCHECK): "BEGIN_CROSSCHECK",
        int(Action.SETTLE_RULING): "SETTLE_RULING",
        int(Action.ISSUE_BADGE): "ISSUE_BADGE",
        int(Action.REVOKE): "REVOKE",
    }.get(int(a), f"A({int(a)})")


_TRANSITION_TABLE = (
    (State.DRAFT, Action.BIND_REGISTRY, State.REGISTRY_BOUND),
    (State.AWAITING_REGISTRY, Action.BIND_REGISTRY, State.REGISTRY_BOUND),
    (State.REGISTRY_BOUND, Action.BEGIN_EXTRACT, State.EXTRACTING),
    (State.EXTRACTING, Action.SETTLE_EXTRACT, State.EXTRACTING),
    (State.EXTRACTING, Action.BEGIN_CROSSCHECK, State.CROSS_CHECKING),
    (State.CROSS_CHECKING, Action.SETTLE_RULING, State.RULED),
    (State.RULED, Action.ISSUE_BADGE, State.BADGED),
    (State.BADGED, Action.REVOKE, State.REVOKED),
    (State.RULED, Action.REVOKE, State.REVOKED),
)


def _resolve_transition(current: int, action: int):
    cur = int(current)
    act = int(action)
    for from_s, act_s, to_s in _TRANSITION_TABLE:
        if int(from_s) == cur and int(act_s) == act:
            return int(to_s)
    return None


def _require_transition(current: int, action: int) -> int:
    target = _resolve_transition(current, action)
    if target is None:
        _bail_expected(
            E_INVALID_TRANSITION,
            current=_state_label(current),
            action=_action_label(action),
        )
    return target


def _extract_field_block(reading, key: str) -> dict:
    if not isinstance(reading, dict):
        _bail_llm(E_LLM_NOT_DICT, where=key)
    block = reading.get(key)
    if not isinstance(block, dict):
        _bail_llm(E_LLM_MISSING_FIELD, field=key)
    return block


class CredentialCheck(gl.Contract):
    registry_authority: Address
    credentials: TreeMap[u32, Credential]
    field_verdicts: TreeMap[str, FieldVerdict]
    holders_index: TreeMap[Address, DynArray[u32]]
    institution_index: TreeMap[str, DynArray[u32]]
    institution_rolls: TreeMap[str, InstitutionRoll]
    transitions: DynArray[TransitionLog]
    next_credential_id: u32
    next_seq: u64
    submitted_total: u32
    ruled_total: u32
    verified_total: u32
    invalid_total: u32
    badged_total: u32
    revoked_total: u32
    blank_u32: DynArray[u32]

    def __init__(self):
        self.registry_authority = gl.message.sender_address
        self.next_credential_id = u32(0)
        self.next_seq = u64(1)
        self.submitted_total = u32(0)
        self.ruled_total = u32(0)
        self.verified_total = u32(0)
        self.invalid_total = u32(0)
        self.badged_total = u32(0)
        self.revoked_total = u32(0)

    def _alloc_seq(self) -> int:
        s = int(self.next_seq)
        self.next_seq = u64(s + 1)
        return s

    def _record_transition(self, cred_id: int, from_state: int, action: int, to_state: int, detail_obj) -> int:
        seq = self._alloc_seq()
        try:
            detail_json = json.dumps(detail_obj, sort_keys=True, ensure_ascii=False, default=str)
        except Exception:
            detail_json = "{}"
        log = TransitionLog(
            seq=u64(seq),
            credential_id=u32(cred_id),
            actor=gl.message.sender_address,
            from_state=u8(int(from_state)),
            action=u8(int(action)),
            to_state=u8(int(to_state)),
            detail=detail_json,
        )
        self.transitions.append(log)
        return seq

    def _apply_transition(self, cred: Credential, cred_id: int, action: int, detail_obj) -> int:
        current = int(cred.state)
        target = _require_transition(current, action)
        seq = self._record_transition(cred_id, current, action, target, detail_obj)
        cred.state = u8(target)
        cred.last_transition_seq = u64(seq)
        history = cred.state_history_summary or ""
        token = f"{_state_label(current)}-{_action_label(action)}->{_state_label(target)}|s{seq};"
        new_history = (history + token)[-1024:]
        cred.state_history_summary = new_history
        return seq

    def _key_field_verdict_id(self, cred_id: int, field_name: str) -> str:
        return f"{int(cred_id)}::{field_name}"

    def _bump_institution(self, cred: Credential, *, mark_ruled: bool, verdict: Verdict, tier: BadgeTier, badge_change: int) -> None:
        key = cred.institution_hash
        roll = self.institution_rolls.get(key)
        if roll is None:
            roll = InstitutionRoll(
                institution=cred.institution,
                institution_hash=key,
                total=u32(0),
                verified=u32(0),
                invalid=u32(0),
                badged=u32(0),
                last_credential_id=u32(0),
            )
        if mark_ruled:
            if verdict == Verdict.VERIFIED:
                roll.verified = u32(int(roll.verified) + 1)
            elif verdict == Verdict.INVALID:
                roll.invalid = u32(int(roll.invalid) + 1)
        if badge_change != 0:
            cur = int(roll.badged) + int(badge_change)
            if cur < 0:
                cur = 0
            roll.badged = u32(cur)
        self.institution_rolls[key] = roll

    def _push_holder_index(self, holder: Address, cred_id: int) -> None:
        if holder not in self.holders_index:
            self.holders_index[holder] = self.blank_u32
        self.holders_index[holder].append(u32(cred_id))

    def _push_institution_index(self, institution_hash: str, cred_id: int) -> None:
        if institution_hash not in self.institution_index:
            self.institution_index[institution_hash] = self.blank_u32
        self.institution_index[institution_hash].append(u32(cred_id))

    def _validate_institution(self, institution: str) -> str:
        s = (institution or "").strip()
        if not s:
            _bail_expected(E_BAD_INSTITUTION)
        if len(s) > INSTITUTION_MAX_LEN:
            _bail_expected(E_INSTITUTION_TOO_LONG, len=len(s), max=INSTITUTION_MAX_LEN)
        return s

    def _validate_cred_text(self, text: str) -> str:
        s = text or ""
        if len(s.strip()) < CRED_TEXT_MIN_LEN:
            _bail_expected(E_BAD_CRED_TEXT, min=CRED_TEXT_MIN_LEN)
        if len(s) > CRED_TEXT_MAX_LEN:
            _bail_expected(E_DOSSIER_TOO_LONG, where="credential", len=len(s), max=CRED_TEXT_MAX_LEN)
        return s

    def _validate_registry_text(self, text: str) -> str:
        s = text or ""
        if len(s.strip()) < REGISTRY_TEXT_MIN_LEN:
            _bail_expected(E_BAD_REGISTRY_TEXT, min=REGISTRY_TEXT_MIN_LEN)
        if len(s) > REGISTRY_TEXT_MAX_LEN:
            _bail_expected(E_DOSSIER_TOO_LONG, where="registry", len=len(s), max=REGISTRY_TEXT_MAX_LEN)
        return s

    @gl.public.write
    def submit_credential(self, institution: str, credential_text: str) -> u32:
        inst = self._validate_institution(institution)
        text = self._validate_cred_text(credential_text)
        cid = int(self.next_credential_id)
        inst_hash = _hash20(inst.lower())
        cred = Credential(
            holder=gl.message.sender_address,
            institution=inst,
            institution_hash=inst_hash,
            submitted_text=text,
            submitted_hash=_hash20(text),
            registry_text="",
            registry_hash="",
            state=u8(int(State.AWAITING_REGISTRY)),
            state_history_summary="",
            registry_matches=u32(0),
            contradiction=False,
            verdict=u8(int(Verdict.UNKNOWN)),
            tier=u8(int(BadgeTier.NONE)),
            badge_ref="",
            rationale="",
            submitted_at_seq=u64(0),
            last_transition_seq=u64(0),
            badged_at_seq=u64(0),
            revoked_at_seq=u64(0),
            registry_attestor="",
            registry_binding_hash="",
            registry_source_type="",
        )
        seq = self._alloc_seq()
        cred.submitted_at_seq = u64(seq)
        cred.last_transition_seq = u64(seq)
        log = TransitionLog(
            seq=u64(seq),
            credential_id=u32(cid),
            actor=gl.message.sender_address,
            from_state=u8(int(State.DRAFT)),
            action=u8(0),
            to_state=u8(int(State.AWAITING_REGISTRY)),
            detail=json.dumps({"event": "submitted", "institution_hash": inst_hash}, sort_keys=True),
        )
        self.transitions.append(log)
        self.credentials[u32(cid)] = cred
        self._push_holder_index(gl.message.sender_address, cid)
        self._push_institution_index(inst_hash, cid)
        roll = self.institution_rolls.get(inst_hash)
        if roll is None:
            roll = InstitutionRoll(
                institution=inst,
                institution_hash=inst_hash,
                total=u32(1),
                verified=u32(0),
                invalid=u32(0),
                badged=u32(0),
                last_credential_id=u32(cid),
            )
        else:
            roll.total = u32(int(roll.total) + 1)
            roll.last_credential_id = u32(cid)
        self.institution_rolls[inst_hash] = roll
        self.submitted_total = u32(int(self.submitted_total) + 1)
        self.next_credential_id = u32(cid + 1)
        return u32(cid)

    def _load_cred(self, cid: u32) -> Credential:
        if cid not in self.credentials:
            _bail_expected(E_UNKNOWN_CREDENTIAL, credential_id=int(cid))
        return self.credentials[cid]

    def _require_holder(self, cred: Credential) -> None:
        if cred.holder != gl.message.sender_address:
            _bail_expected(
                E_NOT_HOLDER,
                expected=_hex_address(cred.holder),
                actor=_hex_address(gl.message.sender_address),
            )

    def _require_registry_authority(self) -> None:
        if gl.message.sender_address != self.registry_authority:
            _bail_expected(
                E_NOT_REGISTRY_AUTHORITY,
                expected=_hex_address(self.registry_authority),
                actor=_hex_address(gl.message.sender_address),
            )

    @gl.public.write
    def attach_registry(self, credential_id: u32, registry_text: str) -> u64:
        self._require_registry_authority()
        cred = self._load_cred(credential_id)
        text = self._validate_registry_text(registry_text)
        if int(cred.state) not in (int(State.DRAFT), int(State.AWAITING_REGISTRY)):
            _bail_expected(E_WRONG_STATE, state=_state_label(int(cred.state)))
        cred.registry_text = text
        cred.registry_hash = _hash20(text)
        cred.registry_attestor = _hex_address(gl.message.sender_address)
        cred.registry_source_type = "REGISTRY_AUTHORITY"
        cred.registry_binding_hash = _hash20(
            f"{int(credential_id)}::{cred.institution_hash}::{cred.submitted_hash}::{cred.registry_hash}::{cred.registry_attestor}"
        )
        seq = self._apply_transition(
            cred,
            int(credential_id),
            int(Action.BIND_REGISTRY),
            {
                "event": "registry_bound",
                "registry_hash": cred.registry_hash,
                "registry_attestor": cred.registry_attestor,
                "registry_source_type": cred.registry_source_type,
                "registry_binding_hash": cred.registry_binding_hash,
            },
        )
        self.credentials[credential_id] = cred
        return u64(seq)

    @gl.public.write
    def transfer_registry_authority(self, new_authority: Address) -> None:
        self._require_registry_authority()
        self.registry_authority = _as_address(new_authority)

    @gl.public.write
    def run_field_extraction(self, credential_id: u32) -> u64:
        cred = self._load_cred(credential_id)
        if int(cred.state) != int(State.REGISTRY_BOUND):
            _bail_expected(E_WRONG_STATE, state=_state_label(int(cred.state)))
        snap = gl.storage.copy_to_memory(cred)
        cred_text = snap.submitted_text[:CRED_TEXT_MAX_LEN]
        reg_text = snap.registry_text[:REGISTRY_TEXT_MAX_LEN]
        institution = snap.institution

        def call_extract():
            prompt = (
                "You are a credential registrar's data-extraction step. The registry side was bound on-chain "
                "by the contract's registry authority; the credential side was submitted by the holder. From the two texts below, locate the "
                "five key fields for each side. Do not judge agreement here; the goal is OBJECTIVE extraction.\n"
                f"Claimed institution: {institution}\n"
                "Fields to extract (FROM BOTH SIDES SEPARATELY): holder_name, institution, program_title, "
                "issue_date, registry_id.\n"
                f"---CREDENTIAL---\n{cred_text}\n---CREDENTIAL---\n"
                f"---REGISTRY---\n{reg_text}\n---REGISTRY---\n"
                'Return strict JSON of shape: {"fields":{'
                '"holder_name":{"credential":"<excerpt or empty>","registry":"<excerpt or empty>"},'
                '"institution":{"credential":"<excerpt>","registry":"<excerpt>"},'
                '"program_title":{"credential":"<excerpt>","registry":"<excerpt>"},'
                '"issue_date":{"credential":"<excerpt>","registry":"<excerpt>"},'
                '"registry_id":{"credential":"<excerpt>","registry":"<excerpt>"}'
                '}}'
            )
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                _bail_llm(E_LLM_NOT_DICT, step="extract")
            fields = raw.get("fields")
            if not isinstance(fields, dict):
                _bail_llm(E_LLM_MISSING_FIELD, key="fields")
            out = {}
            for name in KEY_FIELD_NAMES:
                block = fields.get(name)
                if not isinstance(block, dict):
                    _bail_llm(E_LLM_MISSING_FIELD, field=name)
                out[name] = {
                    "credential": _trim(block.get("credential", ""), 160),
                    "registry": _trim(block.get("registry", ""), 160),
                }
            return {"fields": out}

        def validate_extract(leaders_res):
            if not isinstance(leaders_res, gl.vm.Return):
                return _consensus_on_fault(leaders_res, call_extract)
            data = leaders_res.calldata
            if not isinstance(data, dict):
                return False
            fields = data.get("fields")
            if not isinstance(fields, dict):
                return False
            for name in KEY_FIELD_NAMES:
                blk = fields.get(name)
                if not isinstance(blk, dict):
                    return False
            try:
                mine = call_extract()
            except gl.vm.UserError:
                return False
            return True

        extracted = gl.vm.run_nondet_unsafe(call_extract, validate_extract)
        fields = extracted.get("fields", {})
        cred = self._load_cred(credential_id)
        seq = self._apply_transition(
            cred,
            int(credential_id),
            int(Action.BEGIN_EXTRACT),
            {"event": "extract_started"},
        )
        for name in KEY_FIELD_NAMES:
            blk = fields.get(name, {})
            fv = FieldVerdict(
                field_name=name,
                submitted_excerpt=_trim(blk.get("credential", ""), 160),
                registry_excerpt=_trim(blk.get("registry", ""), 160),
                concord=False,
                conflicts=False,
                confidence=u8(0),
                note="",
            )
            self.field_verdicts[self._key_field_verdict_id(int(credential_id), name)] = fv
        self._apply_transition(
            cred,
            int(credential_id),
            int(Action.SETTLE_EXTRACT),
            {"event": "extract_settled"},
        )
        self.credentials[credential_id] = cred
        return u64(seq)

    @gl.public.write
    def run_cross_check(self, credential_id: u32) -> u64:
        cred = self._load_cred(credential_id)
        if int(cred.state) != int(State.EXTRACTING):
            _bail_expected(E_WRONG_STATE, state=_state_label(int(cred.state)))
        snap = gl.storage.copy_to_memory(cred)
        institution = snap.institution
        per_field_excerpts = {}
        for name in KEY_FIELD_NAMES:
            key = self._key_field_verdict_id(int(credential_id), name)
            if key in self.field_verdicts:
                fv = self.field_verdicts[key]
                per_field_excerpts[name] = {
                    "credential": fv.submitted_excerpt,
                    "registry": fv.registry_excerpt,
                }
            else:
                per_field_excerpts[name] = {"credential": "", "registry": ""}
        excerpts_text = json.dumps(per_field_excerpts, sort_keys=True, ensure_ascii=False)[:3800]

        def call_judge():
            prompt = (
                "You decide, field-by-field, whether each side of a credential / registry pair AGREES, "
                "and whether any pair DIRECTLY CONTRADICTS the other. A missing field on one side is NOT a "
                "contradiction; only an explicit conflict counts (e.g., different holder name for the same id, "
                "different institution for the same registry id, mismatched issue date that cannot be reconciled). "
                "Treat holder_name, institution, program_title, issue_date, and registry_id as identity-critical fields; "
                "do not grant concordance unless the official registry excerpt actually supports the submitted field.\n"
                f"Claimed institution under review: {institution}\n"
                f"Per-field excerpts: {excerpts_text}\n"
                'Return strict JSON with shape: {"per_field":{'
                '"holder_name":{"concord":<bool>,"conflicts":<bool>,"confidence":0-100,"note":"<=160"},'
                '"institution":{...},"program_title":{...},"issue_date":{...},"registry_id":{...}'
                '},"registry_matches":<0-5 int>,"contradiction":<bool>,"rationale":"<=480"}'
            )
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                _bail_llm(E_LLM_NOT_DICT, step="judge")
            per_field = raw.get("per_field")
            if not isinstance(per_field, dict):
                _bail_llm(E_LLM_MISSING_FIELD, key="per_field")
            cleaned = {}
            verified_count = 0
            contra_seen = False
            for name in KEY_FIELD_NAMES:
                block = per_field.get(name)
                if not isinstance(block, dict):
                    _bail_llm(E_LLM_MISSING_FIELD, field=name)
                concord = _coerce_bool(block.get("concord"))
                conflicts = _coerce_bool(block.get("conflicts"))
                if concord is None or conflicts is None:
                    _bail_llm(E_LLM_BAD_BOOL, field=name)
                conf = _coerce_int(block.get("confidence"), 0)
                conf = _clamp(int(conf), 0, 100)
                cleaned[name] = {
                    "concord": bool(concord),
                    "conflicts": bool(conflicts),
                    "confidence": int(conf),
                    "note": _trim(block.get("note", ""), 160),
                }
                if concord and not conflicts:
                    verified_count += 1
                if conflicts:
                    contra_seen = True
            stated_matches = _coerce_int(raw.get("registry_matches"), -1)
            if stated_matches is None or stated_matches < 0 or stated_matches > KEY_FIELD_COUNT:
                _bail_llm(E_LLM_OUT_OF_RANGE, field="registry_matches", got=stated_matches)
            stated_contra = _coerce_bool(raw.get("contradiction"))
            if stated_contra is None:
                _bail_llm(E_LLM_BAD_BOOL, field="contradiction")
            if abs(stated_matches - verified_count) > PER_FIELD_VOTE_TOL:
                stated_matches = verified_count
            stated_contra = bool(stated_contra) or contra_seen
            return {
                "per_field": cleaned,
                "registry_matches": int(stated_matches),
                "contradiction": bool(stated_contra),
                "rationale": _trim(raw.get("rationale", ""), 480),
            }

        def validate_judge(leaders_res):
            if not isinstance(leaders_res, gl.vm.Return):
                return _consensus_on_fault(leaders_res, call_judge)
            data = leaders_res.calldata
            if not isinstance(data, dict):
                return False
            leader_matches = _coerce_int(data.get("registry_matches"), -1)
            if leader_matches is None or leader_matches < 0 or leader_matches > KEY_FIELD_COUNT:
                return False
            leader_contra = _coerce_bool(data.get("contradiction"))
            if leader_contra is None:
                return False
            try:
                mine = call_judge()
            except gl.vm.UserError:
                return False
            my_matches = int(mine.get("registry_matches", 0))
            my_contra = bool(mine.get("contradiction", False))
            if my_contra != bool(leader_contra):
                return False
            if abs(my_matches - leader_matches) > MATCH_VALIDATOR_TOL:
                return False
            leader_verdict = _verdict_from_matches(int(leader_matches), bool(leader_contra))
            mine_verdict = _verdict_from_matches(my_matches, my_contra)
            return int(leader_verdict) == int(mine_verdict)

        judged = gl.vm.run_nondet_unsafe(call_judge, validate_judge)
        per_field = judged.get("per_field", {})
        registry_matches = int(judged.get("registry_matches", 0))
        contradiction = bool(judged.get("contradiction", False))
        rationale = _trim(judged.get("rationale", ""), 480)
        cred = self._load_cred(credential_id)
        begin_seq = self._apply_transition(
            cred,
            int(credential_id),
            int(Action.BEGIN_CROSSCHECK),
            {"event": "crosscheck_started"},
        )
        for name in KEY_FIELD_NAMES:
            key = self._key_field_verdict_id(int(credential_id), name)
            existing = self.field_verdicts.get(key)
            block = per_field.get(name, {})
            if existing is None:
                continue
            existing.concord = bool(block.get("concord", False))
            existing.conflicts = bool(block.get("conflicts", False))
            existing.confidence = u8(_clamp(int(block.get("confidence", 0)), 0, 100))
            existing.note = _trim(block.get("note", ""), 160)
            self.field_verdicts[key] = existing
        verdict = _verdict_from_matches(registry_matches, contradiction)
        tier = _tier_from_matches(registry_matches, contradiction)
        cred.registry_matches = u32(_clamp(registry_matches, 0, KEY_FIELD_COUNT))
        cred.contradiction = bool(contradiction)
        cred.verdict = u8(int(verdict))
        cred.tier = u8(int(tier))
        cred.rationale = rationale
        settle_seq = self._apply_transition(
            cred,
            int(credential_id),
            int(Action.SETTLE_RULING),
            {
                "event": "ruled",
                "registry_matches": int(registry_matches),
                "contradiction": bool(contradiction),
                "verdict": VERDICT_NAMES[int(verdict)],
                "tier": TIER_NAMES[int(tier)],
            },
        )
        self.credentials[credential_id] = cred
        self.ruled_total = u32(int(self.ruled_total) + 1)
        if verdict == Verdict.VERIFIED:
            self.verified_total = u32(int(self.verified_total) + 1)
        elif verdict == Verdict.INVALID:
            self.invalid_total = u32(int(self.invalid_total) + 1)
        self._bump_institution(cred, mark_ruled=True, verdict=verdict, tier=tier, badge_change=0)
        return u64(settle_seq)

    @gl.public.write
    def issue_badge(self, credential_id: u32) -> str:
        cred = self._load_cred(credential_id)
        if int(cred.state) == int(State.BADGED):
            _bail_expected(E_ALREADY_BADGED, credential_id=int(credential_id))
        if int(cred.state) != int(State.RULED):
            _bail_expected(E_WRONG_STATE, state=_state_label(int(cred.state)))
        if int(cred.verdict) != int(Verdict.VERIFIED):
            _bail_expected(
                E_NOT_VERIFIED,
                verdict=VERDICT_NAMES[int(cred.verdict)],
                credential_id=int(credential_id),
            )
        badge_ref = (
            f"VERIFIED-CREDENTIAL#{int(credential_id)}@"
            f"{cred.institution_hash[:16]}|tier={TIER_NAMES[int(cred.tier)]}|"
            f"matches={int(cred.registry_matches)}/{KEY_FIELD_COUNT}|"
            f"holder={_hex_address(cred.holder)[:12]}|sub={cred.submitted_hash[:16]}|"
            f"reg={cred.registry_hash[:16]}"
        )
        cred.badge_ref = badge_ref
        seq = self._apply_transition(
            cred,
            int(credential_id),
            int(Action.ISSUE_BADGE),
            {
                "event": "badge_issued",
                "tier": TIER_NAMES[int(cred.tier)],
                "ref": badge_ref,
            },
        )
        cred.badged_at_seq = u64(seq)
        self.credentials[credential_id] = cred
        self._bump_institution(cred, mark_ruled=False, verdict=Verdict.UNKNOWN, tier=BadgeTier.NONE, badge_change=1)
        self.badged_total = u32(int(self.badged_total) + 1)
        return badge_ref

    @gl.public.write
    def revoke_badge(self, credential_id: u32, reason: str) -> u64:
        cred = self._load_cred(credential_id)
        self._require_holder(cred)
        if int(cred.state) not in (int(State.BADGED), int(State.RULED)):
            _bail_expected(E_WRONG_STATE, state=_state_label(int(cred.state)))
        was_badged = int(cred.state) == int(State.BADGED)
        seq = self._apply_transition(
            cred,
            int(credential_id),
            int(Action.REVOKE),
            {"event": "revoked", "reason": _trim(reason, 240)},
        )
        cred.revoked_at_seq = u64(seq)
        cred.badge_ref = ""
        cred.tier = u8(int(BadgeTier.NONE))
        cred.verdict = u8(int(Verdict.INVALID))
        self.credentials[credential_id] = cred
        if was_badged:
            self._bump_institution(cred, mark_ruled=False, verdict=Verdict.UNKNOWN, tier=BadgeTier.NONE, badge_change=-1)
        self.revoked_total = u32(int(self.revoked_total) + 1)
        return u64(seq)

    @gl.public.view
    def get_credential(self, credential_id: u32) -> Credential:
        return self._load_cred(credential_id)

    @gl.public.view
    def get_registry_authority(self) -> str:
        return _hex_address(self.registry_authority)

    @gl.public.view
    def get_field_verdicts(self, credential_id: u32) -> list:
        out = []
        for name in KEY_FIELD_NAMES:
            key = self._key_field_verdict_id(int(credential_id), name)
            fv = self.field_verdicts.get(key)
            if fv is None:
                continue
            out.append({
                "field": fv.field_name,
                "submitted": fv.submitted_excerpt,
                "registry": fv.registry_excerpt,
                "concord": bool(fv.concord),
                "conflicts": bool(fv.conflicts),
                "confidence": int(fv.confidence),
                "note": fv.note,
            })
        return out

    @gl.public.view
    def get_state_label(self, credential_id: u32) -> str:
        cred = self._load_cred(credential_id)
        return _state_label(int(cred.state))

    @gl.public.view
    def get_verdict_label(self, credential_id: u32) -> str:
        cred = self._load_cred(credential_id)
        return VERDICT_NAMES[int(cred.verdict)]

    @gl.public.view
    def get_tier_label(self, credential_id: u32) -> str:
        cred = self._load_cred(credential_id)
        return TIER_NAMES[int(cred.tier)]

    @gl.public.view
    def get_holder_credentials(self, holder: Address) -> list:
        bucket = self.holders_index.get(holder)
        if bucket is None:
            return []
        out = []
        n = len(bucket)
        i = 0
        while i < n:
            cid = bucket[i]
            cred = self.credentials.get(cid)
            if cred is not None:
                out.append({
                    "credential_id": int(cid),
                    "institution": cred.institution,
                    "state": _state_label(int(cred.state)),
                    "verdict": VERDICT_NAMES[int(cred.verdict)],
                    "tier": TIER_NAMES[int(cred.tier)],
                    "matches": int(cred.registry_matches),
                })
            i += 1
        return out

    @gl.public.view
    def get_institution_roll(self, institution: str) -> dict:
        key = _hash20((institution or "").strip().lower())
        roll = self.institution_rolls.get(key)
        if roll is None:
            return {
                "institution": institution,
                "exists": False,
                "total": 0,
                "verified": 0,
                "invalid": 0,
                "badged": 0,
            }
        return {
            "institution": roll.institution,
            "institution_hash": roll.institution_hash,
            "exists": True,
            "total": int(roll.total),
            "verified": int(roll.verified),
            "invalid": int(roll.invalid),
            "badged": int(roll.badged),
            "last_credential_id": int(roll.last_credential_id),
        }

    @gl.public.view
    def get_institution_credentials(self, institution: str, offset: u32, limit: u32) -> list:
        off = int(offset)
        lim = int(limit)
        if off < 0 or lim <= 0 or lim > 200:
            _bail_expected(E_BAD_OFFSET, offset=off, limit=lim)
        key = _hash20((institution or "").strip().lower())
        bucket = self.institution_index.get(key)
        if bucket is None:
            return []
        out = []
        seen = 0
        emitted = 0
        n = len(bucket)
        i = 0
        while i < n and emitted < lim:
            if seen >= off:
                cid = bucket[i]
                cred = self.credentials.get(cid)
                if cred is not None:
                    out.append({
                        "credential_id": int(cid),
                        "holder": _hex_address(cred.holder),
                        "state": _state_label(int(cred.state)),
                        "verdict": VERDICT_NAMES[int(cred.verdict)],
                        "tier": TIER_NAMES[int(cred.tier)],
                        "matches": int(cred.registry_matches),
                    })
                    emitted += 1
            seen += 1
            i += 1
        return out

    @gl.public.view
    def get_transition_log(self, credential_id: u32, offset: u32, limit: u32) -> list:
        off = int(offset)
        lim = int(limit)
        if off < 0 or lim <= 0 or lim > 200:
            _bail_expected(E_BAD_OFFSET, offset=off, limit=lim)
        out = []
        seen = 0
        emitted = 0
        cid = int(credential_id)
        i = 0
        n = len(self.transitions)
        while i < n and emitted < lim:
            log = self.transitions[i]
            if int(log.credential_id) == cid:
                if seen >= off:
                    out.append({
                        "seq": int(log.seq),
                        "actor": _hex_address(log.actor),
                        "from_state": _state_label(int(log.from_state)),
                        "action": _action_label(int(log.action)),
                        "to_state": _state_label(int(log.to_state)),
                        "detail": log.detail,
                    })
                    emitted += 1
                seen += 1
            i += 1
        return out

    @gl.public.view
    def get_counts(self) -> dict:
        return {
            "submitted_total": int(self.submitted_total),
            "ruled_total": int(self.ruled_total),
            "verified_total": int(self.verified_total),
            "invalid_total": int(self.invalid_total),
            "badged_total": int(self.badged_total),
            "revoked_total": int(self.revoked_total),
            "next_credential_id": int(self.next_credential_id),
            "next_seq": int(self.next_seq),
            "registry_authority": _hex_address(self.registry_authority),
        }

    @gl.public.view
    def list_transition_table(self) -> list:
        out = []
        for from_s, act, to_s in _TRANSITION_TABLE:
            out.append({
                "from_state": _state_label(int(from_s)),
                "action": _action_label(int(act)),
                "to_state": _state_label(int(to_s)),
            })
        return out

    @gl.public.view
    def get_recent_transitions(self, limit: u32) -> list:
        lim = int(limit)
        if lim <= 0 or lim > 500:
            _bail_expected(E_BAD_OFFSET, offset=0, limit=lim)
        out = []
        n = len(self.transitions)
        i = n - 1
        while i >= 0 and len(out) < lim:
            log = self.transitions[i]
            out.append({
                "seq": int(log.seq),
                "credential_id": int(log.credential_id),
                "actor": _hex_address(log.actor),
                "from_state": _state_label(int(log.from_state)),
                "action": _action_label(int(log.action)),
                "to_state": _state_label(int(log.to_state)),
                "detail": log.detail,
            })
            i -= 1
        return out

    @gl.public.view
    def top_institutions(self, limit: u32) -> list:
        lim = int(limit)
        if lim <= 0 or lim > 100:
            _bail_expected(E_BAD_OFFSET, offset=0, limit=lim)
        snapshot = []
        for inst_hash in self.institution_rolls:
            roll = self.institution_rolls[inst_hash]
            snapshot.append((int(roll.total), int(roll.verified), int(roll.badged), roll.institution, inst_hash))
        out = []
        used = [False] * len(snapshot)
        target = min(lim, len(snapshot))
        for _ in range(target):
            best = -1
            best_score = -1
            for i, item in enumerate(snapshot):
                if used[i]:
                    continue
                score = item[0] * 100 + item[1] * 10 + item[2]
                if score > best_score:
                    best_score = score
                    best = i
            if best < 0:
                break
            used[best] = True
            total, verified, badged, name, h = snapshot[best]
            out.append({
                "institution": name,
                "institution_hash": h,
                "total": total,
                "verified": verified,
                "badged": badged,
            })
        return out

    @gl.public.view
    def get_state_summary(self) -> dict:
        counts = {label: 0 for label in STATE_NAMES.values()}
        for cid in self.credentials:
            cred = self.credentials[cid]
            counts[_state_label(int(cred.state))] += 1
        return counts

    @gl.public.view
    def get_verdict_summary(self) -> dict:
        counts = {label: 0 for label in VERDICT_NAMES.values()}
        for cid in self.credentials:
            cred = self.credentials[cid]
            counts[VERDICT_NAMES[int(cred.verdict)]] += 1
        return counts

    @gl.public.view
    def get_tier_summary(self) -> dict:
        counts = {label: 0 for label in TIER_NAMES.values()}
        for cid in self.credentials:
            cred = self.credentials[cid]
            counts[TIER_NAMES[int(cred.tier)]] += 1
        return counts

    @gl.public.view
    def get_badge_text(self, credential_id: u32) -> str:
        cred = self._load_cred(credential_id)
        return cred.badge_ref or ""

    @gl.public.view
    def has_any_credential(self, holder: Address) -> bool:
        bucket = self.holders_index.get(holder)
        if bucket is None:
            return False
        return len(bucket) > 0

    @gl.public.view
    def get_action_labels(self) -> list:
        return [_action_label(int(a)) for a in (
            Action.BIND_REGISTRY,
            Action.BEGIN_EXTRACT,
            Action.SETTLE_EXTRACT,
            Action.BEGIN_CROSSCHECK,
            Action.SETTLE_RULING,
            Action.ISSUE_BADGE,
            Action.REVOKE,
        )]
