<!-- SPDX-License-Identifier: Apache-2.0 -->
# demo2 beat sheet — Sep-4 A2A demo

**Presenter script for the Sep-4 demo.** Reviewed and gated before this was
published; presented live by Jody, with Steven. Published here for the group to
read and run alongside the code.

**What layer this exercises.** This demonstrates the **attestation layer** — the
Agent Action Capsule + AAuth authorization that *rides on* an agent-to-agent
transport. It is **not** an A2A-protocol demo: there are no agent cards, no
JSON-RPC methods, no SSE task lifecycle. The two agents talk in-process and the
"wire" frames are printed, not sent (see the offline/live split below). What is
on trial is what each agent can *prove it did*, not how the bytes moved.

One scenario, **twelve acts**, one script (`narrate.py`). Acts 1-3 are the
**negotiation** — the engaging front. Acts 4-12 are the **payoff** — authority,
two ledgers, and a stranger who trusts neither party. Any of the three screen
splits works off this sheet — the maximal runnable subsumes every
presentation split, so nothing below is gated on which split gets chosen.

The columns that matter are the last two: **what a skeptic rechecks**, and
**what this beat does not prove**. If a beat is narrated without its
right-hand column, it is being oversold.

---

## The one-sentence frame

> **Watch an agent haggle. Then watch a stranger check the receipt.**
> Two suppliers compete; the buyer narrates every move, picks a winner against
> a brief it never reveals — and that winner becomes the counterparty in a
> two-ledger record a stranger who trusts neither party can re-check offline.
> **AAuth says who may act. The capsules record what each did —
> tamper-evidently.** (Integrity, not completeness: this proves each record is
> exactly what was sealed, not that either party wrote down everything — see
> the honest gap below.)

---

## The scenario

Acme Co's purchase-order agent needs 29 widgets. It puts one brief to **two**
suppliers — Frobozz Supply and Globex Corp — and haggles both down over three
rounds, working inside a private brief a human approved before it started.
Frobozz wins; Globex, the runner-up, later gets a much larger bulk order that
**a human refuses**. Each company's agent keeps its own record under its own
identity and its own signing key. Nobody shares a database.

**The pacing is part of the demo.** By default each narrated beat holds ~1.2 s
so the room reads a move before the next one lands. `--step` waits for Enter
(you drive). `--fast` removes the pauses and is what the tests and the
transcript use. `--html` also writes a self-contained `index.html` you can open
with `file://` — same content, browser-legible; the terminal stays primary.

---

## Acts 1-3 — the negotiation (the engaging front)

Scripted and deterministic. Nothing here is sealed as a capsule; what *is*
sealed is a digest of it, in the order capsule that follows. Read the last two
columns out loud.

| # | Beat | On screen | What a skeptic rechecks (the exact field) | Say this |
|---|---|---|---|---|
| 1 | **The brief, the wicket, two suppliers** | The buyer's private constraints printed as three lines, then its SHA-256; one RFQ broadcast to both suppliers; two openers that differ on price *and* terms (Frobozz $52.00/net15/12d, Globex $48.00/net30/21d) | `wicket_digest` in `wicket.json` — recompute SHA-256(JCS(manifest)) yourself and compare it to `model_attestation.compute_attestation.mandate.wicket_digest` on the buyer's `submit_order`. Both suppliers got a byte-identical RFQ frame in `wire.json` | "The ceiling on that screen never leaves this room. What the agent seals is its *fingerprint* — so later you can prove it stayed inside a mandate without the mandate's private numbers ever entering the record." |
| 2 | **Counter-rounds** | Reasoning line, beat, move. Anchors at 60% of *each seller's own* quote ($31.20 / $28.80); reads who moved further; climbs toward the settle and says it is comparing them. **Frobozz moves on terms too** — off its net15 opener to net30, the term the brief requires — so its final $42.00/net30 is a genuine settle, not a swap | Every counter and quote is a frame in `wire.json`, in order, with the arithmetic visible: 60% of the seller's own printed number. `negotiation.json` holds all three rounds and its digest is sealed | "It is anchoring, not insulting. How far a supplier moves off its opener — on price *and* on terms — is the only read it gets on where the floor actually is." |
| 3 | **The wicket check, and the pick** | Globex ends **cheaper** — $41.50 vs $42.00 — and is knocked out on a 21-day lead against a 14-day hard maximum. The agent takes the more expensive offer and says why | Re-grade it yourself: `crossverify.py --bundle evidence --mandate` regrades the winner against the invariants published in `wicket.json` rather than trusting `wicket_result: "pass"`. `accepted_offer_digest` appears on **both** ledgers | "The lowest price is not the winning price. A hard invariant is not the agent's to trade — and the record says which one bit, without saying what the numbers were." |

**The mechanical privacy check.** The ceiling and target strings are searched
for across every wire frame at the end of act 3; the run prints `0 of 13`. It
is a check, not a promise. If it ever prints anything else, the demo asserts
and stops.

**What acts 1-3 do NOT prove — say it before act 4, not after:**

- **The negotiation is scripted.** Fixed ladders in `negotiate.py`, no model
  call, no live counterparties. It shows the *shape* of a haggle. It is not
  evidence that one happened. (This is deliberate: a stage LLM call can hang,
  and the whole demo's value is that it cannot.)
- **The offers are not sealed as capsules.** Only their digests are. An
  *altered* negotiation record stops matching what the order committed to; a
  negotiation nobody wrote down leaves no trace either way. Same
  integrity-not-completeness gap as everything else here.
- **Nobody is bound by any of it.** No offer here is a contract. The
  bilateral handshake in acts 7 and 10 proves key-holders signed; it does not
  make anyone liable.

---

## Acts 4-12 — the payoff, act by act

| # | Beat | On screen | What a skeptic rechecks (the exact field) | What this beat does NOT prove |
|---|---|---|---|---|
| 4 | **AAuth grant requested** | `POST /agent_authorization` wire frame; `request_code` comes back. The `reason` names the vendor **the negotiation picked** and the price it settled on | `grant_type` is `urn:ietf:params:oauth:grant-type:agent_authorization` — the draft's *proposed* URN, not an IANA-registered grant type (RFC 6755), so read it as "AAuth-proposed," the same way we qualify the claim set (draft §4); the `reason` in the response is byte-identical to the one sent — §4 says the AS MUST echo it verbatim, and it reads `PO-7777 ($1218.00, net30) with Frobozz Supply` — the deal that was actually struck, not a blank cheque | That any deployed IdP did this. The AS is a stub in this process. |
| 5 | **Human-in-the-loop consent** | The two scope descriptions the AS *displayed*; approval bound to the `request_code` | §3.2: the **AS** ran the review, not the agent; the agent handled no redirect and rendered no UI. Poll #1 returned `{"error":"authorization_pending"}` (§4) | That a human sat there. `human_consent()` is called by the script. |
| 6 | **Token issued** | Poll #2 returns a standard OAuth token response; the claims are printed | `issued_token_type` = `urn:ietf:params:oauth:token-type:jwt` (§4). The claim set is *not* draft-mandated — §4 says "Details to be filled in" — these are ordinary OAuth 2.1 / RFC 9068 shapes | That the claim names are standardised by AAuth. Say "AAuth-shaped", not "AAuth-specified". |
| 7 | **Bilateral move 1** | `subject_digest` printed in full; the two producer `key_id`s printed side by side | `subject_digest` = SHA-256(JCS(order)). The two `key_id` values are different Ed25519 public keys. `capsule_emit.bilateral.request_payload` is the exact byte string signed | That either key belongs to a real company. Key ownership is bound only to `parties.json`. |
| 8 | **BUY side, incl. the $125k refusal** | 4 capsules on acme-co's ledger: `get_price` → `submit_order` → **`approve_large_order` BLOCKED** → `escalate_to_manager` | `disposition.verdict_class="blocked"`, `effect.status="planned"` (gated, never dispatched), `disposition.approver="human"`, `human_disposed=true`, `chain.parent_capsule_id` links the refusal to the dispatch it denies, and `relation="escalates"` carries the chain **past** the refusal | **Nothing prompted at runtime.** The capsule *records* a denial a human made. Also: **two different orders, and the room will try to merge them.** PO-7777 ($1,218, Frobozz — the one just negotiated) dispatched. PO-7778 ($125,000, 2,500 units) is a separate bulk line routed to **Globex, the RFQ runner-up**, because it priced volume better — and a human refused it over that vendor's approved PO ceiling. Say "different order, different vendor, different outcome" before anyone asks. |
| 9 | **SELL side** | 3 capsules on frobozz-supply's ledger, its own operator name and key; four auth checks printed | `model_attestation.compute_attestation.presented_authority.checks` records signature / audience / scope / expiry, each with its outcome. `operator="frobozz-supply"` and a distinct `key_id` on every row — and that operator string came from the **winner of act 3**, not from a constant: `SellerAgent(operator=winner["seller"])` | That the seller is a real company, or that its checks ran against a real issuer. Stub AS, real Ed25519. |
| 10 | **Bilateral moves 2–4** | State walks `requested → acted → acted → bilateral` | Each move's signed bytes come from `capsule_emit.bilateral`'s canonical payload functions, and each verifies with **real Ed25519** against the same key the party's capsules name. The module's `no_op_verifier` (always passes) and `dict_verifier` (HMAC, "demo only") are **not** used | Non-repudiation in any legal sense. It proves key-holders signed, not that anyone is bound. |
| 11 | **Cross-ledger citation** | Seller's confirm cites the buyer's order id; buyer's close-out cites the seller's confirm id | `chain.parent_capsule_id` on each is the counterparty's `capsule_id` — a content-addressed pointer stored in *my* record and signed under *my* key. Forge-resistance is not in the pointer: it comes from the referenced capsule verifying under the counterparty's key (C2), resolving in the union (C4), and matching `subject_digest` (C5). I can cite any real counterparty capsule; only C5 stops me citing an unrelated one's | That both ledgers are complete. See "the honest gap" below. |
| 12 | **Offline cross-verify + tamper** | 19 checks, 0 failures. Then four tampers, each breaking checks | See the check table below | See the check table below |

---

## The twelve acts map to six capsule fields. That's the whole demo.

| Field | Why a skeptic cares |
|---|---|
| `capsule_id` | A digest over the record's own content. Change a byte, it stops recomputing. |
| `signature` + `key_id` | A COSE_Sign1 envelope over `capsule_id`. Proves the **holder of that key** sealed this exact record. |
| `chain.parent_capsule_id` | Content-addressed citation. Works *across* organisations, because it points at a digest, not a row id. |
| `…compute_attestation.subject_digest` | The shared value that makes two independent records provably about **one** transaction. |
| `…compute_attestation.authority` (buyer) / `…presented_authority` (seller) | The AAuth grant, committed as digests. The raw token is never in here. |
| `…compute_attestation.mandate` | The negotiation, committed as digests: the buyer's private brief (`wicket_digest` + `wicket_result`), the whole negotiation record, and the offer that won. Proves the agent acted inside a mandate **without the mandate's numbers entering the record**. Covered by `capsule_id` and the signature like any other content — the `capsule_id` tamper breaks it too. |

(The `…` above is `model_attestation.` — every one of these lives under
`model_attestation.compute_attestation` in the capsule. Grep the leaf name and
you will find it; the full path is written out in the skeptic columns above.)

---

## What the cross-verifier checks (act 12 in detail)

| Check | Question | Honest limit |
|---|---|---|
| **C1** | Does every `capsule_id` recompute from its own content, and does §5 structure hold? | This is `agent_action_capsule.verify` — Class 1, spec §6. It **does not check any signature**; the neutral verifier excludes the COSE envelope by reference. Signature checking is a separate step. |
| **C2** | Does a COSE_Sign1 envelope over each `capsule_id` verify under the key in `key_id`? | Proves the key-holder sealed it. Does **not** prove who the key belongs to. `capsule_emit`'s own docstring says the same thing. |
| **C3** | Does every record in a ledger carry that party's operator name and that party's key? | Stops a pointer borrowing someone else's track record. Says nothing about whether the operator name is *true* — it is a string in a file. |
| **C4** | With both ledgers unioned, does every chain link resolve? | Reported both ways on purpose: **each ledger alone leaves the cross-ledger citations dangling.** That is the bilateral point, not a defect. |
| **C5** | Same `subject_digest` on both sides; seller cites buyer's order; buyer cites seller's confirm | — |
| **C6** | Do the sealed `iss`/`sub`/`aud`/`scope` digests and the combined `claims_digest` recompute from the separately disclosed claim set? | The disclosure is a separate artefact. Possessing it grants nothing — it carries no signature. |
| **C7** | Does the raw access token appear anywhere in either ledger? | Searched as the whole token **and** as each of its three segments, across both files. |

**The count is still 19, on purpose.** The negotiation's own commitments —
wicket digest, negotiation digest, accepted-offer digest, the regrade of the
winner against the disclosed invariants, and the join from the winning offer to
the `subject_digest` both ledgers sealed — are **six more checks in a separate
opt-in section**: `crossverify.py --bundle evidence --mandate`. They are not
folded into the headline number. A demo whose check count quietly grows is a
demo that has stopped being comparable to the last one, and an earlier version
of this work already had to walk back one overclaim. Promoting these into the
19 is a decision to make out loud, not a side effect.

| `--mandate` row | Question | Honest limit |
|---|---|---|
| wicket digest | Does SHA-256(JCS(`wicket.json`)) equal the digest sealed in the order capsule? | Proves the published manifest is the one that was sealed. Does **not** prove a human ever approved it — `approved_by` is a string in a file. |
| negotiation digest | Does the digest recompute from `negotiation.json`? | Proves the transcript was not edited after the order was sealed. Does **not** prove the negotiation happened; it is scripted. |
| accepted-offer digest | Does it recompute from the winner block, and is the **same** digest on both ledgers? | The same offer fingerprint is sealed onto both ledgers. Note what this is and is not: in this demo one in-process script seals the same in-memory winner block twice, so the match is guaranteed by construction — it shows the *plumbing* that lets two parties commit a shared fingerprint, not two independent parties converging. That independence is stubbed, same as the identity binding. |
| winner regrade | Re-run the buyer's eligibility test against the invariants published in `wicket.json` | Takes nothing on trust — it does not read `wicket_result`, it recomputes it. Limited to the invariants the buyer chose to publish. |
| sealed-order join | Does the order document that hashes to the `subject_digest` match the winning offer line by line? | Closes the loop from "a shared digest" to "a shared, readable deal". |

---

## The tamper beat — four injections, each breaking something different

Run live if the room wants it: `python crossverify.py --bundle evidence --tamper <kind>`

| `--tamper` | What is altered | What breaks |
|---|---|---|
| `capsule_id` | A field added to acme-co's `submit_order` capsule **after** it was sealed | C1 (`capsule_id_mismatch`: recomputed ≠ carried) and C2 (the signature is over the *old* id) |
| `output_digest` | One hex character of the seller's confirm output digest | C1 and C2, same pair — the digest is inside the signed content |
| `cross_citation` | The seller's confirm repointed at a non-existent buyer capsule | C1, C2, C4 (dangling link in the union) and C5 (citation no longer matches) — **four checks**, the loudest failure |
| `authority_scope` | The *disclosed* AAuth scope widened after the fact | C6 on both sides: the recomputed `scope_digest` and `claims_digest` stop matching what was sealed |

**Why a content edit trips BOTH C1 and C2** (a skeptic reasoning abstractly
expects only one): C1 recomputes the `capsule_id` from content and finds it no
longer matches the carried id; C2 checks the COSE_Sign1 signature against that
*recomputed* id, not the carried one, so it fails too. The verifier never
trusts the carried id — which is why editing any field inside the capsule's
canonical content (the §5 JCS preimage the `capsule_id` is computed over), not
just the id field, breaks both. (Envelope/transport metadata excluded from that
preimage by reference — the COSE envelope itself is — is a separate matter; the
signature check, not the content hash, is what covers it.) (Verified in the
executed transcript: the `output_digest` tamper shows `[C1] FAIL` and
`[C2] FAIL`.)

**The line to say:** the record is not a log you have to trust. It is a
structure that stops agreeing with itself the moment anyone edits it.

---

## The honest offline / live-credential split

Two columns. Read the right one out loud; the room will ask anyway.

| Runs for real, right now, offline | Stubbed, or absent, and named as such |
|---|---|
| Capsule sealing (`capsule-emit 0.7.0`, installed from PyPI) | The AAuth **Authorization Server** — an in-process stub. Its Ed25519 key is real and its JWS genuinely verifies; nothing about it was deployed, discovered, or operated. |
| Class-1 payload verify (`agent-action-capsule 0.2.0`) | The **identity binding**. No agent card, no JWKS URL, no DNS record, no DANE pin. `key_id → operator` is bound only by this bundle's `parties.json`. |
| Producer COSE_Sign1 signature check under `key_id` | The **transport**. Agents talk in-process; the "wire" frames are printed, not sent. |
| Real Ed25519 on all four bilateral protocol moves | The **anchor / witness**. No checkpoint is submitted anywhere. |
| Token audience / scope / expiry / signature enforcement — *against the stub AS's own issuer key* | The **human**. Nothing prompts at runtime, on either the AAuth consent or the $125k refusal. |
| The four tamper detections | The **negotiation**. Two suppliers with fixed offer ladders in `negotiate.py`; no model, no counterparties, no transport. Deterministic on purpose. |
| The wicket privacy check — the ceiling and target strings really are searched for across every wire frame | The **wicket's provenance**. `approved_by: dana@acme-co.example` is a string in a JSON file. The digest proves the manifest was not altered; nothing proves a human wrote it. |
| The `--mandate` regrade — a stranger recomputes the eligibility decision instead of reading `wicket_result` | The **PII flow** of §3.1. Only element *names* ever move; no PII value exists in this demo, so the hallucination argument is described, not exercised. |

**What swapping in a live IdP costs:** an issuer URL, a JWKS URL, and client
credentials — plus fixing the claim-name mapping and canonicalization the
unspecified AAuth claim schema will pin down. The capsule layer itself does not
move — `authority_commitment()` takes a claim set and does not care where it
came from.

---

## The honest gap — say it before someone else does

**Integrity, not completeness.** Every check above proves that what you are
looking at is exactly what was sealed and has not been altered. **None of them
proves a party did not simply decline to write a record.** Closing that
omission gap takes a consistency check against an independently obtained log
checkpoint — the same gap `jody-seat.md` states up front for the live
`agent.epistemic.sh` seat, stated the same way here.

---

## Vocabulary discipline for the room

- **Sealed** and **content-addressed**. Records are *sealed*; a `capsule_id`
  is a *content address*. Say "signed" only about the specific COSE_Sign1
  envelope over `capsule_id`, and say in the same breath that it proves
  key-holding, not key-ownership.
- **"Verified" needs a qualifier.** C1 and C2 are different checks. "The
  capsule verified", without saying which one, is the overclaim an earlier
  version of this work already had to walk back.
- **No trust-scoring vocabulary.** No "trust score", "reputation", "moat", or
  ranking language. The record and the mechanism only. What anyone concludes
  from the records is their business.
- **Open ≠ adopted.** `draft-rosenberg-oauth-aauth-01` is an individual
  Internet-Draft, work in progress, not WG-adopted. So is
  `draft-mih-scitt-agent-action-capsule-04`. Neither is a standard, and the
  bilateral protocol (`draft-mih-agent-bilateral-attestation-00`) is an
  individual draft too.
- **Disclose the agent assistance.** This packet was built by an agent under
  human direction, and the code says so.


---

## Presenter runbook — carried forward from the 8/20 goose dry-run

The prior demo's dry-run (`financial_demo/NOTES.md`) found operational gotchas.
Demo #2 fixes the worst one by construction and inherits the rest — say these,
they save an awkward moment.

**The biggest last-demo risk cannot happen here: this demo has no network.**
The goose *live* path had four unguarded `urlopen` calls and no error handling —
a slow or unreachable anchor would hang ~30s then die with a traceback on stage.
`narrate.py` opens **no socket at all** (`test_offline.py` bricks the socket
layer and it still passes), so there is no live path to fail and no `--no-anchor`
fallback to remember. There is nothing to rehearse against a flaky network.

**Six gotchas worth pre-empting — four carried forward, two new:**

1. **4 capsules on the buy side, but a 3-link chain.** `get_price` is sealed as
   an FYI and is deliberately *not* chained — a read-only lookup has nothing to
   confirm. The chain is `submit_order → blocked → escalate`. If someone counts
   four and you said "chain of three," that's why — say it first.
2. **Capsule IDs are minted live and differ on every run** (each commits a
   microsecond timestamp and a fresh UUID). **Do not pre-print any capsule ID**
   on a slide, handout, or permalink — whatever is on screen was minted seconds
   ago. Authentic, but fatal for pre-baked material.
3. **UTF-8 terminal required.** Output uses box-drawing and check glyphs; a
   broken locale raises `UnicodeEncodeError` mid-run. Confirm `locale` shows a
   UTF-8 charset on the presenting machine first.
4. **It no longer runs *too* fast — but know which mode you are in.** The
   default holds ~1.2 s between narrated beats, which puts the negotiation at
   roughly 40 seconds of watchable haggling. A few ways to be wrong about
   this, so check before you present:
   - `--step` waits for **Enter** between beats. This is the setting for a
     live room: you drive, and you can talk over a beat as long as you like.
   - `--fast` (or `FAST=1`) removes every pause. Use it for a dry run, never
     for the room.
   - `--pace <seconds>` sets the beat length explicitly (default ~1.2 s) — and,
     because it is explicit, it *overrides* the auto-off below. Use it when you
     want a fixed pace regardless of where output is going.
   - **Pauses turn themselves off when stdout is not a terminal.** Piping to
     `tee` or a file gives you the fast run whether you asked for it or not.
     If you want the beats *and* a log, use `--step` or pass `--pace`
     explicitly, which overrides the auto-detect.

   `--step` degrades to `--fast` if stdin is not a terminal, so a headless
   runner cannot hang waiting for an Enter that will never come. That is the
   deliberate trade: a demo that cannot hang beats a demo that always waits.

5. **`--html` is an also, not an instead.** It writes a self-contained
   `index.html` next to the bundle — inline CSS, no script, no `href`, no
   `src`, no CDN — that opens with `file://` on a machine with no network.
   Good for the hallway conversation after, or a second screen. The terminal
   run is still the demo. `narrate.py` greps the file it just wrote for every
   fetching construct and prints `(checked)`; if that ever says otherwise, do
   not open it in front of anyone.

6. **Two new things to say unprompted, both in the closing block.** The
   negotiation is scripted, and the offers are not sealed as capsules — only
   their digests are. Say both before someone in the room says them for you.

(The "nothing prompts at runtime" point is already in Act 8 — the capsules
record decisions a human already made; you are not staging a live approval UI.)
