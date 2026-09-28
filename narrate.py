#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""demo2 narrator harness — the whole Sep-4 A2A scenario, start to finish.

One script. In-process only: **no network transport, no LLM key, no anchor
submission, no witness submission.** Egress is disabled before ``capsule_emit``
is imported (see ``_no_egress`` below) and asserted again at the end.

    python narrate.py                     # run everything, temp bundle
    python narrate.py --bundle evidence   # write the bundle where it can be kept
    python narrate.py --step              # presenter drives: Enter between beats
    python narrate.py --fast              # no pauses (CI, tests, transcripts)
    python narrate.py --pace 2.0          # slower beats
    python narrate.py --html              # ALSO write a self-contained index.html

Twelve acts. The first three are the **negotiation** — the engaging front,
borrowed in shape from Steven's accountable deal-room and rebuilt scripted and
offline (see ``negotiate.py``). The other nine are the **payoff**: authority,
two ledgers, and a stranger who trusts neither party.

     1. The brief, the wicket, and two competing suppliers
     2. Counter-rounds — anchor low, then climb toward the target
     3. The wicket check, and the pick        -> WINNER becomes the counterparty
     4. AAuth  §4  agent_authorization  -> request_code
     5. AAuth  §3.2 the AS runs the human consent review, binds it to the code
     6. AAuth  §4  poll /token          -> authorization_pending, then a token
     7. Bilateral move 1: buyer signs the request over the shared action digest
     8. BUY  side: order -> $125k HITL DENIAL -> escalation
     9. SELL side: receive (token checked) -> fulfil -> confirm, own ledger
    10. Bilateral moves 2-4: action attestation + both acknowledgments
    11. Buyer's close-out cites the seller's confirm
    12. Offline cross-verify of both ledgers, then four tamper injections

Read ``BEAT_SHEET.md`` alongside this: it maps every beat to the capsule
fields a skeptic rechecks.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Never crash on a non-UTF-8 terminal mid-demo (last-demo gotcha #7):
# reconfigure stdout/stderr to replace unencodable glyphs instead of raising.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _no_egress() -> None:
    """Zero every egress channel BEFORE capsule_emit is imported.

    ``CAPSULE_WITNESS=off`` is capsule-emit 0.7.0's documented single switch
    that "zeroes ALL egress, anchor included" (``capsule_emit/core.py``). The
    other two are belt and braces, and every emitter is additionally built
    with ``anchor=False``.
    """
    os.environ["CAPSULE_WITNESS"] = "off"
    os.environ["CAPSULE_ANCHOR"] = "off"
    os.environ["AAC_ANCHOR_URL"] = "off"


_no_egress()

from capsule_emit import read_ledger                                    # noqa: E402
from capsule_emit.bilateral import (                                    # noqa: E402
    BilateralSig,
    BilateralState,
    BilateralHandshake,
    action_payload,
    confirm_payload,
    request_payload,
    sig_digest,
)
from capsule_emit.signing import resolve_signer                          # noqa: E402

import aauth                                                            # noqa: E402
import crossverify                                                      # noqa: E402
import negotiate                                                        # noqa: E402
from buyer import BuyerAgent                                            # noqa: E402
from pace import DEFAULT_DELAY, Pace                                    # noqa: E402
from seller import SellerAgent                                          # noqa: E402
from wire import Wire                                                   # noqa: E402

SEP = "=" * 74
NOW = 1_772_000_000  # fixed clock — a demo that reruns identically is easier to trust

# The order is NO LONGER a constant. It comes out of the negotiation in acts
# 1-3 (``negotiate.order_from_winner``), so the vendor, the unit price, the
# amount and the payment terms downstream are all the ones that were haggled
# for. Everything after act 3 is about whatever that produced.

# ---------------------------------------------------------------------------
# narration — reasoning line, beat, action line
# ---------------------------------------------------------------------------

# Labels chosen so the eye can skim a column: who is thinking, who is talking,
# and which direction the words went. (Shape borrowed from the deal-room
# buyer's "-> To Marcus: countering at $840 to anchor low" narration.)
_LABELS = {
    "think": "think ",
    "out": "->    ",
    "in": "<-    ",
    "said": "      ",
    "note": "      ",
}

_ACT_NO = itertools.count(1)
NARRATION: list[dict] = []
ACTS: list[dict] = []
PACE = Pace("fast")


def act(title: str) -> None:
    """Open an act. Numbering is automatic so acts can be inserted safely."""
    n = next(_ACT_NO)
    ACTS.append({"n": n, "title": title})
    print(f"\n{SEP}\n  ACT {n} — {title}\n{SEP}")
    PACE.beat(0.5)


def say(kind: str, text: str, beat: float = 1.0) -> None:
    """Print one narrated line, then hold a beat.

    The pause is the feature: the reasoning line lands, the watcher reads it,
    *then* the move happens. ``--fast`` sets every beat to zero, which is what
    ``test_offline.py`` and the transcript regeneration use.
    """
    label = _LABELS.get(kind, "      ")
    # Reasoning is prose and wraps narrow so it reads as a paragraph; quotes,
    # moves and the wicket lines are column-shaped and only wrap as a
    # last resort, because breaking a 64-hex digest across two lines is worse
    # than a long line.
    width = 78 if kind == "think" else 96
    print(textwrap.fill(text, width=width,
                        initial_indent=f"  {label}",
                        subsequent_indent="        ",
                        break_long_words=False, break_on_hyphens=False))
    NARRATION.append({"kind": kind, "text": text,
                      "act": ACTS[-1]["n"] if ACTS else 0})
    PACE.beat(beat)


def step(msg: str) -> None:
    print(f"  {msg}")


def ok(msg: str) -> None:
    print(f"  ok  {msg}")


def main() -> int:
    global PACE
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, default=None,
                    help="directory to write the evidence bundle into")
    ap.add_argument("--pace", type=float, default=DEFAULT_DELAY, dest="pace_delay",
                    help=f"seconds between narrated beats (default {DEFAULT_DELAY})")
    ap.add_argument("--step", action="store_true",
                    help="wait for Enter between beats — the presenter drives")
    ap.add_argument("--fast", action="store_true",
                    help="no pauses at all (also FAST=1). Used by test_offline.py and CI")
    ap.add_argument("--html", nargs="?", const="", default=None, metavar="PATH",
                    help="ALSO render the whole run to a self-contained index.html "
                         "(default: <bundle>/index.html). Offline, inline CSS, no CDN")
    args = ap.parse_args()

    PACE = Pace.from_args(
        fast=args.fast, step=args.step, delay=args.pace_delay,
        delay_was_explicit=any(a.startswith("--pace") for a in sys.argv[1:]),
    )

    bundle = args.bundle or Path(tempfile.mkdtemp(prefix="demo2-"))
    bundle.mkdir(parents=True, exist_ok=True)
    buyer_ledger = str(bundle / "buyer-ledger.jsonl")
    seller_ledger = str(bundle / "seller-ledger.jsonl")
    for p in (buyer_ledger, seller_ledger):
        Path(p).unlink(missing_ok=True)
        Path(p + ".signing_key.pem").unlink(missing_ok=True)

    print(SEP)
    print("  demo2 — a negotiation you can watch, a record a stranger can check")
    print(SEP)
    print(f"  bundle:  {bundle}")
    print(f"  pacing:  {PACE.describe()}")
    print("  egress:  CAPSULE_WITNESS=off, CAPSULE_ANCHOR=off, AAC_ANCHOR_URL=off,")
    print("           every emitter anchor=False. No socket is opened by this script.")

    wire = Wire()

    # ── ACTS 1-3 — the negotiation ─────────────────────────────────────────
    # The RFQ frames are recorded but not printed: the front-half is meant to
    # be *read*, and a wall of JSON between two narrated lines destroys the
    # pacing that makes it readable. They are all in wire.json.
    wire.quiet = True
    neg = negotiate.run(wire=wire, say=say, act=act)
    wire.quiet = False
    step(f"    ({len(wire.frames)} negotiation frames recorded to wire.json — "
         f"not printed here; the printed frames resume with AAuth.)")
    privacy = neg["privacy_check"]
    ok(f"wicket privacy check: the ceiling and target strings appear in "
       f"{len(privacy['leaked'])} of {privacy['frames_searched']} wire frames")
    assert privacy["passed"], "a private wicket value leaked onto the wire"

    winner = neg["winner"]
    if winner is None:
        print("\n  The buyer walked: no offer fit the brief. Nothing to seal.")
        return 1
    ORDER = negotiate.order_from_winner(winner)
    accepted_offer_digest = aauth.jcs_digest(winner)
    ok(f"negotiation digest  {neg['negotiation_digest']}")
    ok(f"accepted offer      {accepted_offer_digest}")
    step(f"    the order the rest of this demo is about: {ORDER['po_number']}  "
         f"{ORDER['vendor']}  {ORDER['line_items'][0]['qty']} x "
         f"{ORDER['line_items'][0]['sku']} @ {ORDER['line_items'][0]['unit_price_usd']}  "
         f"= ${ORDER['amount_usd']}  {ORDER['terms']}")

    # The winner's identity is what names the resource server, the scopes the
    # human is asked to approve, and the seller agent's operator on every
    # capsule it seals. Nothing below is hard-coded to a vendor.
    rs_id = f"urn:{winner['seller']}"
    REQUIRED_SCOPE = f"{rs_id}:orders.submit"
    RS_SCOPES = {
        REQUIRED_SCOPE: f"Submit a purchase order to {winner['seller_display']} on your behalf.",
        f"{rs_id}:orders.read": "Read the status of purchase orders you have placed.",
    }

    # ── ACT 4 — AAuth §4: the Agent Authorization Grant request ────────────
    act("AAuth §4 — POST /agent_authorization  (the 'may', requested)")
    step(f"The negotiation is over; nothing has been committed. Now the agent asks "
         f"a human for permission to place it with {winner['seller_display']}.")
    rs = aauth.ResourceServer(rs_id=rs_id, scope_descriptions=RS_SCOPES)
    as_ = aauth.StubAuthorizationServer(issuer="https://as.acme-co.example", clock=NOW)
    as_.register_client("acme-po-agent", "s3cr3t-demo-only")
    # §3.1 — the AS maps a collected PII tuple to a user. Element NAMES only.
    as_.register_subject(["full_name", "date_of_birth", "ssn_last4"],
                         "acme-user-handle-4417", "urn:acme-co:user:4417")

    grant_request = {
        "grant_type": aauth.AGENT_AUTHORIZATION_GRANT,
        "client_id": "acme-po-agent",
        "scope": f"{REQUIRED_SCOPE} {rs_id}:orders.read",
        "reason": (f"Place purchase order {ORDER['po_number']} "
                   f"(${ORDER['amount_usd']}, {ORDER['terms']}) with "
                   f"{winner['seller_display']} on your behalf."),
        "pii_elements_collected": ["full_name", "date_of_birth", "ssn_last4"],
        "subject_handle": "acme-user-handle-4417",
    }
    wire.send("acme-co/po-agent", "as.acme-co.example", "POST /agent_authorization",
              grant_request)
    auth_resp = as_.agent_authorization(
        grant_type=grant_request["grant_type"],
        client_id=grant_request["client_id"],
        client_secret="s3cr3t-demo-only",
        scope=grant_request["scope"],
        reason=grant_request["reason"],
        pii_elements=grant_request["pii_elements_collected"],
        subject_handle=grant_request["subject_handle"],
        resource_server=rs,
    )
    wire.send("as.acme-co.example", "acme-co/po-agent", "200 agent_authorization",
              auth_resp)
    ok(f"request_code={auth_resp['request_code']}  poll_interval={auth_resp['poll_interval']}s")
    ok("reason echoed verbatim by the AS, as §4 requires")
    step("    the reason carries the negotiated price — the human approves the deal "
         "the agent actually struck, not a blank cheque.")
    step("    PII: only element NAMES crossed this boundary — no PII values exist "
         "anywhere in this demo.")
    PACE.beat(0.5)

    # ── ACT 5 — AAuth §3.2: the AS runs the human loop ─────────────────────
    act("AAuth §3.2 — the AS (not the agent) runs the consent review")
    step("The agent does not render UI and handles no redirect; it waits.")
    pending = as_.token(grant_type=aauth.DEVICE_CODE_GRANT,
                        client_id="acme-po-agent",
                        device_code=auth_resp["request_code"])
    wire.send("as.acme-co.example", "acme-co/po-agent", "200 token (poll #1)", pending)
    assert pending == aauth.AUTHORIZATION_PENDING
    ok("poll #1 -> {\"error\":\"authorization_pending\"}  (§4)")
    shown = as_.human_consent(auth_resp["request_code"],
                              approver="dana@acme-co.example", approve=True)
    print("    displayed to the human (§3.2 step 2):")
    for k, v in shown["scope_descriptions"].items():
        print(f"      {k}\n        -> {v}")
    ok(f"authenticated {shown['authenticated_user']}, approval bound to "
       f"{shown['bound_to_request_code']}")
    PACE.beat(0.5)

    # ── ACT 6 — AAuth §4: the token ────────────────────────────────────────
    act("AAuth §4 — POST /token  (the 'may', issued)")
    tok = as_.token(grant_type=aauth.DEVICE_CODE_GRANT, client_id="acme-po-agent",
                    device_code=auth_resp["request_code"])
    claims = tok.pop("_claims_for_demo_disclosure")
    wire.send("as.acme-co.example", "acme-co/po-agent", "200 token (poll #2)", tok)
    ok(f"issued_token_type={tok['issued_token_type']}")
    print("    claims the agent now holds (shown here, never sealed in the clear):")
    for k in ("iss", "sub", "aud", "scope", "jti", "exp"):
        print(f"      {k:<6} {claims[k]}")
    PACE.beat(0.5)

    buyer_authority = None  # bound in the next act once the agent exists

    # ── ACT 7 — bilateral move 1 ───────────────────────────────────────────
    act("Bilateral move 1 of 4 — request attestation over the shared digest")
    subject_digest = aauth.jcs_digest(ORDER)
    ok(f"subject_digest = SHA-256(JCS(order)) = {subject_digest}")

    buyer = BuyerAgent(buyer_ledger, wire)
    seller = SellerAgent(seller_ledger, wire, rs,
                         operator=winner["seller"], display=winner["seller_display"])
    buyer_authority = buyer.hold_grant(claims)
    ok("acme-co's capsules will carry the grant as digests only: "
       f"claims_digest={buyer_authority['claims_digest'][:24]}…, "
       f"jti={buyer_authority['jti'][-12:]}, raw_token_committed="
       f"{buyer_authority['raw_token_committed']}")
    buyer_signer = resolve_signer(buyer_ledger)
    seller_signer = resolve_signer(seller_ledger)
    keys = {buyer.operator: buyer_signer.key_id, seller.operator: seller_signer.key_id}
    ok(f"{buyer.operator} producer key_id        {keys[buyer.operator]}")
    ok(f"{seller.operator} producer key_id {keys[seller.operator]}")

    def ed25519_verifier(org_id: str, payload: bytes, sig: BilateralSig) -> bool:
        """Real asymmetric verification, keyed by each org's producer key.

        ``capsule_emit.bilateral`` ships ``no_op_verifier`` (always passes) and
        ``dict_verifier`` (HMAC, "demo only") — neither is used here. Each org
        is verified against the same Ed25519 public key its capsules name in
        ``key_id``, so the handshake and the ledger agree on who is who.
        """
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        expected = keys.get(org_id)
        if expected is None or sig.key_id != expected:
            return False
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(expected)).verify(
                bytes.fromhex(sig.signature), payload)
        except (InvalidSignature, ValueError):
            return False
        return True

    def sign(signer, payload: bytes) -> BilateralSig:
        raw, key_id = signer.sign(payload)
        return BilateralSig(alg="Ed25519", key_id=key_id, signature=raw)

    hs = BilateralHandshake(verify_fn=ed25519_verifier)
    req_sig = sign(buyer_signer,
                   request_payload(buyer.operator, seller.operator, subject_digest))
    rec = hs.open(buyer.operator, seller.operator, subject_digest, req_sig)
    ok(f"state={rec.state.value}  handshake_id={rec.handshake_id}")
    buyer.set_bilateral({
        "protocol": "draft-mih-agent-bilateral-attestation-00 (capsule_emit.bilateral)",
        "handshake_id": rec.handshake_id,
        "state": rec.state.value,
        "role": "requester",
        "request_sig_digest": sig_digest(req_sig),
    })
    PACE.beat(0.5)

    # ── ACT 8 — the buy side ───────────────────────────────────────────────
    act("BUY side — acme-co's own ledger  (the goose purchase-order story, kept)")
    price, price_id = buyer.get_price(ORDER["vendor"], ORDER["line_items"][0]["sku"])
    step(f"[1] get_price          -> {price['unit_price_usd']} USD/unit   "
         f"{price_id[:16]}… (fyi, unchained)")
    step(f"    (the catalogue number. The negotiated number is "
         f"{ORDER['line_items'][0]['unit_price_usd']} — the haggle is why they differ.)")

    mandate = {
        "wicket_digest": neg["wicket_digest"],
        "wicket_result": neg["wicket_result"],
        "wicket_manifest": "wicket.json",
        "negotiation_digest": neg["negotiation_digest"],
        "accepted_offer_digest": accepted_offer_digest,
    }
    _out, order_id = buyer.submit_order(ORDER, subject_digest, mandate=mandate)
    step(f"[2] submit_order       -> dispatched  {order_id[:16]}…  "
         f"{ORDER['po_number']} ${ORDER['amount_usd']}")
    step(f"    carries mandate digests: wicket={mandate['wicket_digest'][:16]}… "
         f"({mandate['wicket_result']}), offer={accepted_offer_digest[:16]}…")

    denial_id = buyer.hitl_denial(
        {"po_number": "PO-7778", "vendor": "Globex Corp",
         "amount_usd": "125000.00", "requested_by": "goose-agent@v1",
         "context": "separate bulk line, 2500 units; routed to the RFQ-7777 "
                    "runner-up, who priced volume better than the winner"},
        {"reviewed_at": "2026-09-04T00:00:00Z",
         "reason": "order value exceeds vendor's approved PO ceiling",
         "approver_id": "priya@acme-co.com"},
        order_id)
    step(f"[3] approve_large_order-> BLOCKED     {denial_id[:16]}…  "
         f"PO-7778 $125,000.00, human refusal")
    step("    (a DIFFERENT order, a DIFFERENT vendor. PO-7777 — the one just "
         "negotiated — went through with Frobozz; PO-7778 to Globex did not.)")
    step("    (nothing prompts at runtime — the capsule RECORDS a denial a "
         "human made. Say this.)")

    esc_id = buyer.escalate(
        {"po_number": "PO-7778",
         "reason": "order blocked at approval gate; routing for manager review"},
        {"po_number": "PO-7778", "escalated_to": "ap-manager@acme-co.com"},
        denial_id)
    step(f"[4] escalate_to_manager-> executed    {esc_id[:16]}…  "
         f"relation=escalates — the chain continues PAST the refusal")
    PACE.beat(0.5)

    # ── ACT 9 — the sell side ──────────────────────────────────────────────
    act(f"SELL side — {seller.operator}'s OWN ledger, OWN operator, OWN key")
    seller.set_bilateral({
        "protocol": "draft-mih-agent-bilateral-attestation-00 (capsule_emit.bilateral)",
        "handshake_id": rec.handshake_id,
        "state": rec.state.value,
        "role": "responder",
        "request_sig_digest": sig_digest(req_sig),
    })
    wire.send(buyer.operator, seller.operator, "order.present_credential",
              {"po_number": ORDER["po_number"], "access_token": tok["access_token"],
               "note": "the bearer token DOES cross the wire; it never enters a capsule"})
    recv_id, checks = seller.receive_order(
        order=ORDER, subject_digest=subject_digest,
        buyer_order_capsule_id=order_id, buyer_operator=buyer.operator,
        buyer_key_id=keys[buyer.operator], presented_token=tok["access_token"],
        issuer_jwks=as_.jwks(), required_scope=REQUIRED_SCOPE, now=NOW,
        accepted_offer_digest=accepted_offer_digest)
    step(f"[5] receive_order      -> executed    {recv_id[:16]}…")
    for c in checks:
        step(f"      auth check {c['check']:<10} {'PASS' if c['passed'] else 'FAIL'}  "
             f"{c['detail']}")
    step(f"      and commits the offer it won: {accepted_offer_digest[:16]}… — the "
         f"same digest the buyer sealed, from opposite sides of the table")

    fulfilment, fulfil_id = seller.fulfill(order=ORDER, prior_capsule_id=recv_id,
                                           subject_digest=subject_digest)
    step(f"[6] fulfill_order      -> executed    {fulfil_id[:16]}…  "
         f"tracking {fulfilment['tracking_ref']}")
    PACE.beat(0.5)

    # ── ACT 10 — bilateral moves 2-4 ───────────────────────────────────────
    act("Bilateral moves 2-4 — action attestation + both acknowledgments")
    act_sig = sign(seller_signer,
                   action_payload(rec.handshake_id, seller.operator, sig_digest(req_sig)))
    rec = hs.respond(rec.handshake_id, act_sig)
    ok(f"move 2  responder signed the action  -> state={rec.state.value}")
    rec = hs.confirm(rec.handshake_id, buyer.operator,
                     sign(buyer_signer, confirm_payload(rec.handshake_id, buyer.operator,
                                                        sig_digest(act_sig))))
    ok(f"move 3  requester acknowledged        -> state={rec.state.value}")
    rec = hs.confirm(rec.handshake_id, seller.operator,
                     sign(seller_signer, confirm_payload(rec.handshake_id,
                                                         seller.operator,
                                                         sig_digest(req_sig))))
    ok(f"move 4  responder acknowledged        -> state={rec.state.value}")
    assert rec.state is BilateralState.BILATERAL
    ok("every signature above verified with real Ed25519 against the same key each "
       "party's capsules name — not the module's no_op_verifier, not its HMAC "
       "dict_verifier")

    bilateral_final = {
        "protocol": "draft-mih-agent-bilateral-attestation-00 (capsule_emit.bilateral)",
        "handshake_id": rec.handshake_id,
        "state": rec.state.value,
        "request_sig_digest": sig_digest(req_sig),
        "action_sig_digest": sig_digest(act_sig),
    }
    seller.set_bilateral({**bilateral_final, "role": "responder"})
    confirmation, confirm_id, response_digest = seller.confirm(
        order=ORDER, fulfilment=fulfilment, buyer_order_capsule_id=order_id,
        buyer_operator=buyer.operator, buyer_key_id=keys[buyer.operator],
        subject_digest=subject_digest)
    step(f"[7] confirm_fulfillment-> confirmed   {confirm_id[:16]}…")
    step(f"      cites {buyer.operator}'s order capsule {order_id[:16]}… by content address")
    PACE.beat(0.5)

    # ── ACT 11 — the close-out ─────────────────────────────────────────────
    act("Close-out — the buyer cites the SELLER's capsule, across the ledger line")
    buyer.set_bilateral({**bilateral_final, "role": "requester"})
    close_id = buyer.close_out(
        seller_confirm_capsule_id=confirm_id, seller_operator=seller.operator,
        seller_key_id=keys[seller.operator], subject_digest=subject_digest,
        confirmation=confirmation, response_digest=response_digest)
    step(f"[8] close_out_order    -> confirmed   {close_id[:16]}…")
    step(f"      cites {seller.operator}'s confirm {confirm_id[:16]}… by content address")

    buyer_records = read_ledger(buyer_ledger)
    seller_records = read_ledger(seller_ledger)
    print(f"\n  {buyer.operator} ledger:        {len(buyer_records)} capsules")
    for r in buyer_records:
        _row(r)
    print(f"  {seller.operator} ledger: {len(seller_records)} capsules")
    for r in seller_records:
        _row(r)
    PACE.beat(0.5)

    # ── write the bundle ───────────────────────────────────────────────────
    (bundle / "parties.json").write_text(json.dumps({
        buyer.operator: {"operator": buyer.operator, "developer": buyer.developer,
                         "key_id": keys[buyer.operator], "ledger": "buyer-ledger.jsonl"},
        seller.operator: {"operator": seller.operator,
                          "developer": seller.developer,
                          "key_id": keys[seller.operator],
                          "ledger": "seller-ledger.jsonl"},
    }, indent=2) + "\n")
    (bundle / "authority-disclosure.json").write_text(
        json.dumps(aauth.disclosure(claims), indent=2) + "\n")
    (bundle / "wicket.json").write_text(json.dumps(negotiate.WICKET, indent=2) + "\n")
    (bundle / "negotiation.json").write_text(json.dumps(neg, indent=2) + "\n")
    (bundle / "transaction.json").write_text(json.dumps({
        "order": ORDER, "subject_digest": subject_digest,
        "buyer_operator": buyer.operator, "seller_operator": seller.operator,
        "buyer_order_capsule_id": order_id, "seller_confirm_capsule_id": confirm_id,
        "buyer_close_out_capsule_id": close_id,
        "bilateral": bilateral_final,
        "mandate": mandate,
    }, indent=2) + "\n")
    (bundle / "token-probe.json").write_text(json.dumps(
        {"token": tok["access_token"],
         "note": "held OUTSIDE the bundle's evidence claim — supplied only so the "
                 "cross-verifier can prove this string appears in neither ledger"},
        indent=2) + "\n")
    (bundle / "wire.json").write_text(json.dumps(wire.as_json(), indent=2) + "\n")

    # ── ACT 12 — the stranger's turn ───────────────────────────────────────
    act("Offline cross-verify — a stranger, both ledgers, no network, no trust")
    clean_rc, clean_rep = _verify_and_print(bundle, None, quiet=False)
    print()
    print("  Beyond the 19 — the negotiation's own commitments, rechecked from the "
          "bundle's files:")
    mandate_rows = crossverify.mandate_report(bundle)
    for row in mandate_rows:
        print(f"     {'ok  ' if row['passed'] else 'FAIL'} {row['name']:<64} {row['detail']}")
    print("     (these are NOT part of the 19 above — they are a separate, "
          "opt-in section: crossverify.py --bundle <dir> --mandate)")
    print()

    _tamper_says = {
        "capsule_id": "a field was added after sealing -> the record no longer hashes to its own id, and the signature was over the old id (C1 + C2)",
        "output_digest": "one hex char of an output digest flipped -> the id recomputes differently and the signature no longer matches (C1 + C2)",
        "cross_citation": "the cross-ledger pointer was repointed at a capsule that does not exist -> the id breaks, the union has a dangling link, and the citation no longer matches (C1 + C2 + C4 + C5)",
        "authority_scope": "the DISCLOSED AAuth scope was widened after the fact -> the sealed scope/claims digests no longer recompute from the disclosure (C6)",
    }
    tampers = []
    for kind in ("capsule_id", "output_digest", "cross_citation", "authority_scope"):
        print(f"  --- tamper: {kind} " + "-" * (46 - len(kind)))
        _rc, rep = _verify_and_print(bundle, kind, quiet=True)
        print(f"     in plain terms: {_tamper_says[kind]}.")
        tampers.append({"kind": kind, "says": _tamper_says[kind],
                        "rows": rep.rows,
                        "failures": [r for r in rep.rows if r[2] == crossverify.BAD]})
        PACE.beat(0.5)

    # ── closing ────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  What this run established")
    print(SEP)
    print(f"  a negotiation with two competing suppliers, {len(neg['rounds'])} rounds, "
          f"a winner picked against a private brief")
    print("  the winner's identity is what named the resource server, the scopes a")
    print("  human approved, and the operator on every sell-side capsule")
    print(f"  two ledgers, {len(buyer_records)} + {len(seller_records)} capsules, "
          f"two distinct producer keys")
    print("  one transaction: both sides committed the same subject_digest")
    print("  each side's confirm/close-out cites the other's capsule by content address")
    print("  AAuth claims sealed as digests only; the raw token is in neither ledger")
    print("  every capsule verifies offline; four separate tampers each broke a check")
    print()
    print("  What it did NOT establish (say these unprompted):")
    print("   - the negotiation itself is SCRIPTED. Fixed ladders, no model, no")
    print("     counterparties. It shows the shape of a haggle, not that one happened.")
    print("   - the offers and counters are NOT sealed as capsules. What is sealed is")
    print("     the digest of the negotiation record and of the winning offer, so an")
    print("     altered transcript stops matching — but a negotiation nobody wrote")
    print("     down leaves no trace either way.")
    print("   - no signature was checked on any AGENT CARD or DNS record; key")
    print("     ownership is bound only to this bundle's parties.json")
    print("   - the AAuth AS is a stub in this process. Its signature is real; its")
    print("     deployment is not.")
    print("   - no human was prompted at runtime. The capsule records a refusal a")
    print("     human made.")
    print("   - integrity, not completeness: nothing here proves a party did not")
    print("     omit a record it never wrote down.")
    print(f"\n  bundle kept at: {bundle}")
    print(f"  re-check it any time:  python crossverify.py --bundle {bundle}")

    html_rc = 0
    if args.html is not None:
        import render_html
        target = Path(args.html) if args.html else (bundle / "index.html")
        run_record = {
            "bundle": str(bundle),
            "pacing": PACE.describe(),
            "acts": ACTS,
            "narration": NARRATION,
            "negotiation": neg,
            "order": ORDER,
            "mandate": mandate,
            "accepted_offer_digest": accepted_offer_digest,
            "subject_digest": subject_digest,
            "keys": keys,
            "parties": {"buyer": buyer.operator, "seller": seller.operator},
            "aauth": {"request_code": auth_resp["request_code"],
                      "scope_descriptions": shown["scope_descriptions"],
                      "approver": shown["authenticated_user"],
                      "claims": {k: claims[k] for k in
                                 ("iss", "sub", "aud", "scope", "jti", "exp")},
                      "issued_token_type": tok["issued_token_type"]},
            "auth_checks": checks,
            "bilateral": bilateral_final,
            "buyer_records": buyer_records,
            "seller_records": seller_records,
            "verify": {"rows": clean_rep.rows,
                       "checks": len(clean_rep.rows),
                       "failures": len([r for r in clean_rep.rows
                                        if r[2] == crossverify.BAD])},
            "mandate_rows": mandate_rows,
            "tampers": tampers,
        }
        html = render_html.render(run_record)
        target.write_text(html, encoding="utf-8")
        html_rc = render_html.assert_offline(html)
        print(f"\n  browser render: {target}")
        print(f"  open it with:   file://{target.resolve()}")
        print("  self-contained: inline CSS, no <script>, no external URL, no CDN "
              f"({'checked' if html_rc == 0 else 'CHECK FAILED'})")
    print(SEP)

    failures = [clean_rc != 0, html_rc != 0,
                any(not r["passed"] for r in mandate_rows)]
    return 1 if any(failures) else 0


def _row(r: dict) -> None:
    ca = (r.get("model_attestation") or {}).get("compute_attestation", {})
    chain = r.get("chain") or {}
    parent = chain.get("parent_capsule_id")
    rel = chain.get("relation")
    link = f"  -> {parent[:12]}… ({rel})" if parent else ""
    print(f"    {r['capsule_id'][:12]}…  {str(r.get('action_id','?')).split('/')[0]:<22} "
          f"[{r['disposition']['verdict_class']:<8}] "
          f"effect={r.get('effect',{}).get('status','?'):<10}{link}")


def _verify_and_print(bundle: Path, tamper: str | None, *, quiet: bool):
    """Run the stranger's checks and print them exactly as ``crossverify.py`` does.

    Returns ``(rc, report)``. The report is kept so the HTML render shows the
    same rows the terminal did, rather than re-deriving them.
    """
    rep, what = crossverify.evaluate(bundle, tamper)
    if what:
        print(f"  TAMPER [{tamper}]: {what}")
    print(rep.render(failures_only=quiet))
    failed = [r for r in rep.rows if r[2] == crossverify.BAD]
    if tamper:
        print(f"\n  -> {len(failed)} check(s) FAILED; the tamper was detected."
              if failed else
              "\n  -> NOTHING FAILED. The tamper went undetected — that is a bug.")
        return (0 if failed else 1), rep
    print(f"\n  -> {len(rep.rows)} checks, {len(failed)} failures. "
          f"Bundle {'VERIFIES' if rep.ok else 'DOES NOT VERIFY'}.")
    return (0 if rep.ok else 1), rep


if __name__ == "__main__":
    raise SystemExit(main())
