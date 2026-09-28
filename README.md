<!-- SPDX-License-Identifier: Apache-2.0 -->
# demo2 — a negotiation you can watch, a record a stranger can check

Built during the Action State Group engagement and first run in a partner testbed on 2026-09-04; published here as-is, Apache-2.0.

**Demo code, not a shipped adapter.** Built for the Sep-4 A2A demo (demo #2,
requested by Steven on the 9/2 meeting recordings). It is staged here as an
`examples/`-shaped packet: nothing under `capsule_emit/` changes, and nothing
here is proposed as a supported surface.

> **AAuth says who may act. The capsule proves what they did.**

Acme Co's purchase-order agent puts one brief to **two competing suppliers**,
narrates its reasoning before every move, haggles them both down over three
rounds, and picks a winner against a private brief it never reveals — then
declines the *cheaper* final offer, because that one breaks a hard constraint
in its mandate. The winner becomes the counterparty for everything that
follows. Each side keeps its own record, under its own operator identity and
its own signing key, in its own file. A stranger who trusts neither of them can
check the whole transaction offline — and tampering with any single record
breaks the check loudly.

The negotiation is the engaging front. The verification is the payoff.

## Run it

The fastest path is `bash RUN.sh` — it builds the venv the first time, then
plays the paced terminal run. `bash RUN.sh --browser` renders and opens the
self-contained page instead. Or do it by hand:

```bash
python -m venv .venv && . .venv/bin/activate
pip install "capsule-emit>=0.7.0" "agent-action-capsule>=0.2.0"

python narrate.py --bundle evidence     # the whole scenario, ~1.2 s beats
python narrate.py --step                # presenter drives: Enter between beats
python narrate.py --fast                # no pauses (what the tests use)
python narrate.py --pace 2.0            # slower beats
python narrate.py --bundle evidence --html   # ALSO write evidence/index.html

python crossverify.py --bundle evidence          # re-check the bundle standalone
python crossverify.py --bundle evidence --mandate  # + the negotiation's commitments
python crossverify.py --bundle evidence --tamper cross_citation
python test_offline.py                  # the same run with sockets bricked
```

### Pacing

The narration is meant to be **watched**, not scrolled past: a reasoning line
lands, you read it, *then* the move happens. Default is a ~1.2 s beat between
narrated lines. `--step` waits for Enter instead, so a presenter drives.
`--fast` (or `FAST=1`) removes the pauses — that is what `test_offline.py`, CI
and the transcript regeneration use, so they stay instant. **Pauses also turn
themselves off automatically when stdout is not a terminal**, so piping to a
file is fast without asking; pass `--pace` explicitly to override that.
`--step` degrades to `--fast` when stdin is not a terminal, so a headless
runner cannot hang waiting for an Enter. The pauses are `time.sleep` and
`input` — timing only, never a socket.

### Browser

`--html` *also* renders the whole run to a self-contained `index.html`: status
badges, an offer card per supplier per round, the narration verbatim, the
wicket grading, the sealed-binding box, both ledgers, the 19 checks and the
four tampers. Inline CSS, **no `<script>`, no `href`, no `src`, no CDN, no web
font** — it opens with `file://` on a machine with no network.
`render_html.assert_offline()` greps the rendered document for every one of
those constructs and `narrate.py` runs it on the file it just wrote. The
terminal path stays the default and the primary; the browser render is an
**also**, not a replacement.

No LLM key. No network. No transport. `narrate.py` sets `CAPSULE_WITNESS=off`,
`CAPSULE_ANCHOR=off` and `AAC_ANCHOR_URL=off` **before** importing
`capsule_emit`, and every emitter is built `anchor=False`. `test_offline.py`
replaces `socket.socket`, `socket.create_connection`, `socket.getaddrinfo` and
`ssl.SSLContext.wrap_socket` with functions that raise, then runs the whole
demo — it completes, so nothing reached for a connection.

Versions this was executed against are in [`transcript.md`](transcript.md):
`capsule-emit 0.7.0`, `agent-action-capsule 0.2.0`, both installed from PyPI
into a fresh venv.

## Files

| File | What it is |
|---|---|
| [`BEAT_SHEET.md`](BEAT_SHEET.md) | **Read this first if you are presenting.** Every beat mapped to the capsule field a skeptic rechecks, plus the honest offline-vs-live-credential split. |
| [`transcript.md`](transcript.md) | Verbatim stdout of three executed runs, with versions and exit codes. |
| `RUN.sh` | One-command runner: builds the venv once, then plays the paced run. `--browser` renders and opens the page instead. |
| `narrate.py` | The one script. Twelve acts, start to finish. |
| `negotiate.py` | The negotiation front-half: two competing suppliers with deterministic offer ladders, three narrated counter-rounds, and the buyer's private wicket. Engagement borrowed from the accountable deal-room; scripted and offline so it cannot hang. |
| `pace.py` | The beat between narrated moves. `pause` / `step` / `fast`, and the rules for which one you get. |
| `render_html.py` | The `--html` render. One pure function, no I/O, plus the offline check that greps its own output. |
| `aauth.py` | The AAuth seam — a stub Authorization Server modelling `draft-rosenberg-oauth-aauth-01`, and the digest-only authority commitment. |
| `buyer.py` | Acme Co's agent. The `examples/goose-capsule` purchase-order story (including the $125k human refusal) plus a cross-ledger close-out. |
| `seller.py` | The winning supplier's agent — its operator name comes from whoever won act 3, not from a constant. Its own operator identity, its own ledger, its own key. |
| `crossverify.py` | The stranger's tool. Imports neither agent; reads only the published bundle. |
| `wire.py` | In-process "wire" that prints the JSON frames between agents. |
| `test_offline.py` | The offline proof. |
| `evidence/` | A committed bundle from an executed run — re-checkable as-is. Includes `wicket.json` (the published brief), `negotiation.json` (all three rounds) and `index.html` (the browser render of that same run). |

## What the demo actually shows

1. **The negotiation, new.** One RFQ to two suppliers; two different openers
   (Frobozz $52.00/net15/12-day, Globex $48.00/net30/21-day); the buyer
   anchoring at 60% of *each seller's own* quote, reading who moved further,
   climbing to $40.00 and telling both it is comparing them. Then the beat the
   whole front-half exists for: **Globex ends cheaper — $41.50 against
   $42.00 — and loses**, because its 21-day lead breaks a hard invariant in the
   buyer's brief. The agent takes the more expensive offer and says why. What
   is sealed into the resulting order is the brief's *digest* and a pass/fail,
   never its numbers.
2. **The buy side, unchanged.** `get_price` → `submit_order` →
   **`approve_large_order` blocked by a human at $125,000** →
   `escalate_to_manager` with `relation="escalates"`. The chain continues past
   the refusal; a denial is as provable as a performance. This is the existing
   `examples/goose-capsule` story, kept because it already carries a genuine
   refusal.
3. **The sell side, new.** A counterparty agent with a different operator name
   and a different Ed25519 producer key: `receive_order` (which validates the
   presented token) → `fulfill_order` → `confirm_fulfillment`.
4. **Bilateral cross-verify.** The seller's confirm cites the buyer's order
   capsule by content address; the buyer's close-out cites the seller's
   confirm. Both sides commit the same `subject_digest`. The four-move
   handshake from `capsule_emit.bilateral` runs alongside, signed with **real
   Ed25519** keyed to each party's producer key — not the module's
   `no_op_verifier`, not its HMAC `dict_verifier`.
5. **The auth seam.** The AAuth Agent Authorization Grant (§4) issues a scoped
   token after a human consent review the **AS** runs (§3.2). The token's
   `iss`/`sub`/`aud`/`scope` are sealed into the capsules **as digests only**;
   the raw token never enters a capsule, and `crossverify.py` proves that
   mechanically by searching both ledger files for the token and each of its
   three segments.
6. **The mandate, checkable by a stranger.** `crossverify.py --mandate`
   recomputes the wicket digest from the published manifest, recomputes the
   negotiation digest, confirms **both** ledgers carry the same
   accepted-offer digest (in this demo one in-process script seals it onto both,
   so the match is by construction — it shows the plumbing for a shared
   fingerprint, not two independent parties converging; that independence is
   stubbed, same as the identity binding), **re-grades the
   winner** against the disclosed invariants rather than trusting
   `wicket_result: "pass"`, and joins the winning offer to the `subject_digest`
   both parties committed. Six rows, in their own section — deliberately not
   folded into the headline 19.
7. **Tamper.** Four injections — a post-seal edit, a flipped output digest, a
   repointed cross-ledger citation, a widened disclosed scope — each break a
   named check.

## What it does not show

Stated here, in the beat sheet, and out loud in the room:

- **The negotiation is scripted.** Fixed offer ladders in `negotiate.py`, no
  model call, no live counterparties, no transport. Same offers, same winner,
  same digest, every run. That is deliberate — a live LLM call can hang on
  stage, and the entire value of this demo is that it cannot — but it means
  acts 1-3 show the *shape* of a haggle, not evidence that one happened.
- **The offers and counters are not sealed as capsules.** Only their digests
  are, in the order capsule. An *altered* negotiation record stops matching; a
  negotiation nobody wrote down leaves no trace either way. Same
  integrity-not-completeness gap as everything else here.
- **The wicket's provenance is not proved.** `approved_by` is a string in a
  JSON file. The digest proves the manifest was not altered after the fact; it
  does not prove a human approved it.
- **The AAuth AS is a stub in this process.** Its Ed25519 key is real and its
  JWS genuinely verifies, so the seller's audience/scope/expiry/signature
  checks are real checks. Nothing about it was deployed, discovered or
  operated. Swapping in a live IdP is an issuer URL, a JWKS URL and client
  credentials; nothing in the capsule layer moves.
- **No identity binding.** There is no agent card, no JWKS URL, no DNS record,
  no DANE pin. `key_id → operator` is bound only by this bundle's
  `parties.json`. The producer signature proves the **holder of a key** sealed
  a record — never who that key belongs to.
- **No A2A protocol on the wire.** Despite the name, this is not an
  A2A-transport demo: no agent cards, no JSON-RPC methods, no SSE task
  lifecycle. The two agents run in-process and the `wire.json` frames are
  *printed*, not sent. What this exercises is the attestation layer — capsules
  + AAuth — that would *ride on* an A2A transport; the transport itself is
  stubbed, deliberately, so nothing can hang or reach the network.
- **Two kinds of "verify".** `agent_action_capsule.verify` is Class-1 payload
  verification (spec §6): `capsule_id` recomputes, §5 structure holds. It
  deliberately does **not** check any signature. The COSE_Sign1 check is a
  separate call (`capsule_emit.signing.verify_capsule_signature`). The
  cross-verifier runs both and labels them separately. Never say "it verified"
  without saying which.
- **No human is prompted at runtime**, on either the AAuth consent or the
  $125k refusal. The capsule *records* a decision a human made.
- **Integrity, not completeness.** Nothing here proves a party did not simply
  decline to write a record down.
- **Nothing here is a standard.** `draft-rosenberg-oauth-aauth-01`,
  `draft-mih-scitt-agent-action-capsule-04` and
  `draft-mih-agent-bilateral-attestation-00` are individual Internet-Drafts,
  work in progress, not WG-adopted.

## Sources read before building

- `aauth-draft.txt` — `draft-rosenberg-oauth-aauth-01`, "AAuth - Agentic
  Authorization OAuth 2.1 Extension" (Rosenberg/White, 19 Oct 2025). §2
  framework, §3.1 basic token flow and the PII-sparseness argument, §3.2
  human-in-the-loop, §4 the detailed grant flow. Cited by section throughout
  `aauth.py`.
- `steven-traceability.md` — the authorization-vs-traceability split this demo
  is built around: *"Authorization = may, Traceability = did"*, and its
  warnings that a valid capsule does not prove the action was correct and that
  tamper-**evident** is not tamper-**proof**. Both are honoured in the beat
  sheet's right-hand columns.
- `jody-seat.md` — the seat: portable, verifiable action history as
  **records, not scores**; subject-bound both ways (operator + key
  thumbprint); and the stated integrity-not-completeness gap, restated here in
  the same words.
- `examples/goose-capsule/` and `examples/aauth-capsule-interop/` in
  `capsule-emit` — the buy-side story and the shared-`subject_digest` pattern
  this demo extends across two ledgers.
- `action-state-group/accountable-dealroom` — **the inspiration for acts
  1-3.** Read `skills/dj-buyer/SKILL.md` (narrate every move before you make
  it; anchor at 60%; the private wicket and its digest),
  `app/sellers/marcus.py` and `nadia.py` (two deterministic sellers with
  genuinely different offers), `app/routes/hire.py` (offer/counter rounds) and
  `app/routes/room_view.py` (the server-rendered room: status badges, offer
  cards, the sealed-binding box — the shape `render_html.py` borrows). What is
  **not** borrowed is its risk surface: its sellers are live agents on a poll
  loop behind an HTTP service and its buyer is an LLM working `curl`. Ours is
  scripted, in-process and socket-free, because this demo's whole claim is
  that nothing in it can hang or reach the network.

## Disclosure

Prepared with AI-agent assistance under human direction.
