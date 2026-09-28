#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bilateral cross-verify — what a stranger runs, offline, trusting neither party.

Reads a bundle directory and answers one question per check. Nothing here
imports ``buyer.py`` or ``seller.py``; it reads only the published artefacts,
the way a third party would.

Usage::

    python crossverify.py --bundle evidence/
    python crossverify.py --bundle evidence/ --tamper capsule_id
    python crossverify.py --bundle evidence/ --tamper output_digest
    python crossverify.py --bundle evidence/ --tamper cross_citation
    python crossverify.py --bundle evidence/ --tamper authority_scope

Bundle contents (all produced by ``narrate.py``)::

    buyer-ledger.jsonl        acme-co's capsules
    seller-ledger.jsonl       frobozz-supply's capsules
    parties.json              each party's operator name + producer key_id
    authority-disclosure.json the AAuth claim values the capsules commit to
    transaction.json          the shared subject_digest and the cited ids

What each check does and does not prove
---------------------------------------
C1 **payload verify** (``agent_action_capsule.verify``, Class 1 / spec §6):
   ``capsule_id`` recomputes from the record's own content, and the §5
   structural rules hold. It does **not** check any signature — the neutral
   verifier excludes the COSE envelope by reference. That is a separate step.

C2 **producer signature** (``capsule_emit.signing.verify_capsule_signature``):
   a real COSE_Sign1 envelope over ``capsule_id`` verifies under the key named
   in ``key_id``. This proves *the holder of that key sealed this exact
   record*. It does **not** prove who that key belongs to — key ownership is
   an identity-binding layer (agent card / JWKS / DNS-anchored name), and this
   demo binds it only to a locally published ``parties.json``. Say so.

C3 **subject binding**: every record in a ledger carries that party's operator
   name and that party's key_id, so a pointer cannot borrow the other party's
   track record.

C4 **chain resolution**: with the two ledgers unioned as one store, every
   ``chain.parent_capsule_id`` resolves. Each ledger *alone* leaves the
   cross-ledger links dangling — that is the point, and C4 reports both.

C5 **bilateral binding**: both parties committed the same ``subject_digest``,
   the seller's confirm cites the buyer's order capsule by content address,
   and the buyer's close-out cites the seller's confirm.

C6 **authority commitment**: the sealed ``sub``/``scope``/``aud``/``iss``
   digests, and the combined ``claims_digest``, recompute from the separately
   disclosed claim values.

C7 **raw-token absence**: the access token — and every one of its three
   segments — appears nowhere in either ledger file.

Nothing in here touches the network.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

from agent_action_capsule import verify
from capsule_emit.signing import verify_capsule_signature

OK = "PASS"
BAD = "FAIL"


def jcs_digest(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, str]] = []

    def add(self, check: str, name: str, passed: bool, detail: str) -> bool:
        self.rows.append((check, name, OK if passed else BAD, detail))
        return passed

    @property
    def ok(self) -> bool:
        return all(r[2] == OK for r in self.rows)

    def render(self, failures_only: bool = False) -> str:
        rows = [r for r in self.rows if r[2] == BAD] if failures_only else self.rows
        if not rows:
            return "  (no rows)"
        width = max(len(r[1]) for r in rows)
        lines = []
        for check, name, verdict, detail in rows:
            mark = "ok  " if verdict == OK else "FAIL"
            lines.append(f"  [{check}] {mark} {name.ljust(width)}  {detail}")
        return "\n".join(lines)


def compute_attestation(rec: dict) -> dict:
    return (rec.get("model_attestation") or {}).get("compute_attestation", {}) or {}


def find(records: list[dict], action_prefix: str) -> dict | None:
    for r in records:
        if str(r.get("action_id", "")).split("/")[0] == action_prefix:
            return r
    return None


# ---------------------------------------------------------------------------
# Tamper injections — each one must break exactly one named check, loudly
# ---------------------------------------------------------------------------


def apply_tamper(kind: str, buyer: list[dict], seller: list[dict], disclosure: dict) -> str:
    """Mutate the bundle in memory. Returns a description of what changed."""
    if kind == "capsule_id":
        rec = find(buyer, "submit_order")
        rec["tool_output_note"] = "altered after sealing"
        return ("added a field to acme-co's submit_order capsule after it was "
                "sealed (the classic post-hoc edit)")
    if kind == "output_digest":
        rec = find(seller, "confirm_fulfillment")
        ca = rec["model_attestation"]["compute_attestation"]
        d = ca["agent_output_digest"]
        ca["agent_output_digest"] = d[:-1] + ("0" if d[-1] != "0" else "1")
        return "flipped one hex character of frobozz-supply's confirm output digest"
    if kind == "cross_citation":
        rec = find(seller, "confirm_fulfillment")
        rec["chain"]["parent_capsule_id"] = "f" * 64
        return ("repointed the seller's confirm at a different (non-existent) "
                "buyer capsule")
    if kind == "authority_scope":
        rs = disclosure["scope"].split()[0].rsplit(":", 1)[0]
        disclosure["scope"] = disclosure["scope"] + f" {rs}:orders.refund"
        return ("widened the disclosed AAuth scope after the fact "
                "(claiming a permission the grant never carried)")
    raise SystemExit(f"unknown --tamper kind {kind!r}")


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def cross_verify(
    buyer: list[dict],
    seller: list[dict],
    parties: dict,
    disclosure: dict,
    transaction: dict,
    raw_ledger_text: dict[str, str],
    token_probe: dict | None,
) -> Report:
    rep = Report()
    # Party names come from the bundle, not from a constant in this file: the
    # counterparty is whichever seller WON the negotiation, so a verifier that
    # hard-codes a vendor name is checking the wrong thing the day the ladders
    # change. transaction.json names both sides; older bundles fall back.
    buyer_party = transaction.get("buyer_operator", "acme-co")
    seller_party = transaction.get("seller_operator", "frobozz-supply")
    ledgers = {buyer_party: buyer, seller_party: seller}
    union = buyer + seller

    # -- C1: Class-1 payload verify, each record, each ledger, no store ------
    for party, records in ledgers.items():
        bad = []
        for r in records:
            vr = verify(r)
            if not vr.ok:
                bad.append((r.get("capsule_id", "?")[:12], [f.detail for f in vr.findings]))
        rep.add(
            "C1", f"{party}: payload verify ({len(records)} capsules)", not bad,
            "capsule_id recomputes + §5 structure holds; signature NOT checked here"
            if not bad else f"{len(bad)} failed: {bad}",
        )

    # -- C2: producer signature ----------------------------------------------
    for party, records in ledgers.items():
        bad = [r.get("capsule_id", "?")[:12] for r in records
               if not verify_capsule_signature(r)]
        rep.add(
            "C2", f"{party}: producer COSE_Sign1 signature", not bad,
            "each capsule_id signed under the key named in key_id"
            if not bad else f"{len(bad)} failed: {bad}",
        )

    # -- C3: subject binding --------------------------------------------------
    for party, records in ledgers.items():
        expected_key = parties[party]["key_id"]
        ops = {r.get("operator") for r in records}
        keys = {r.get("key_id") for r in records}
        good = ops == {party} and keys == {expected_key}
        rep.add(
            "C3", f"{party}: subject-bound (operator + key_id)", good,
            f"operator={sorted(ops)} key_id={expected_key[:16]}…"
            if good else f"MIXED operator={sorted(ops)} keys={[k[:12] for k in keys]}",
        )
    distinct = parties[buyer_party]["key_id"] != parties[seller_party]["key_id"]
    rep.add("C3", "two parties, two distinct producer keys", distinct,
            f"{parties[buyer_party]['key_id'][:16]}… vs "
            f"{parties[seller_party]['key_id'][:16]}…")

    # -- C4: chain resolution, per-ledger then unioned ------------------------
    ids_union = {r["capsule_id"] for r in union}
    for party, records in ledgers.items():
        own = {r["capsule_id"] for r in records}
        dangling = [
            (r["capsule_id"][:12], r["chain"]["parent_capsule_id"][:12])
            for r in records
            if r.get("chain") and r["chain"].get("parent_capsule_id") not in own
        ]
        # Dangling links in a single ledger are EXPECTED — they are the
        # cross-ledger citations. Reported, not failed.
        rep.add(
            "C4", f"{party}: links resolvable within its own ledger alone", True,
            "all links internal" if not dangling
            else f"{len(dangling)} cross-ledger citation(s) unresolvable alone "
                 f"(expected): {dangling}",
        )
    unresolved = [
        (r["capsule_id"][:12], r["chain"]["parent_capsule_id"][:12])
        for r in union
        if r.get("chain") and r["chain"].get("parent_capsule_id") not in ids_union
    ]
    rep.add("C4", "union of both ledgers: every chain parent resolves", not unresolved,
            f"{len(union)} capsules, 0 dangling links" if not unresolved
            else f"unresolved: {unresolved}")

    # -- C5: bilateral binding ------------------------------------------------
    order = find(buyer, "submit_order")
    confirm = find(seller, "confirm_fulfillment")
    close = find(buyer, "close_out_order")
    have_all = all(x is not None for x in (order, confirm, close))
    if not rep.add("C5", "the three bilateral capsules are present", have_all,
                   "submit_order / confirm_fulfillment / close_out_order"
                   if have_all else "one or more missing"):
        return rep

    sd = transaction["subject_digest"]
    sd_buyer = compute_attestation(order).get("subject_digest")
    sd_seller = compute_attestation(confirm).get("subject_digest")
    rep.add("C5", "both parties committed the SAME subject_digest",
            sd_buyer == sd_seller == sd, f"{sd[:24]}…"
            if sd_buyer == sd_seller == sd
            else f"buyer={sd_buyer} seller={sd_seller} expected={sd}")

    cites_order = confirm.get("chain", {}).get("parent_capsule_id") == order["capsule_id"]
    rep.add("C5", "seller's confirm cites buyer's order by content address",
            cites_order,
            f"{confirm['capsule_id'][:12]}… -> {order['capsule_id'][:12]}…"
            if cites_order
            else f"cites {confirm.get('chain', {}).get('parent_capsule_id', '?')[:12]}…, "
                 f"expected {order['capsule_id'][:12]}…")

    cites_confirm = close.get("chain", {}).get("parent_capsule_id") == confirm["capsule_id"]
    rep.add("C5", "buyer's close-out cites seller's confirm by content address",
            cites_confirm,
            f"{close['capsule_id'][:12]}… -> {confirm['capsule_id'][:12]}…"
            if cites_confirm
            else f"cites {close.get('chain', {}).get('parent_capsule_id', '?')[:12]}…, "
                 f"expected {confirm['capsule_id'][:12]}…")

    # -- C6: authority commitment ---------------------------------------------
    committed = {k: disclosure[k] for k in ("iss", "sub", "aud", "scope")}
    expected_claims_digest = jcs_digest(committed)
    slots = [
        (f"{buyer_party} (held grant)", compute_attestation(order).get("authority")),
        (f"{seller_party} (presented grant)",
         compute_attestation(confirm).get("presented_authority")),
    ]
    for label, slot in slots:
        if slot is None:
            rep.add("C6", f"{label}: authority slot present", False, "absent")
            continue
        mismatches = [
            k for k in ("iss", "sub", "aud", "scope")
            if slot.get(f"{k}_digest") != jcs_digest(disclosure[k])
        ]
        combined_ok = slot.get("claims_digest") == expected_claims_digest
        jti_ok = slot.get("jti") == disclosure["jti"]
        good = not mismatches and combined_ok and jti_ok
        rep.add("C6", f"{label}: claim digests recompute from disclosure", good,
                f"iss/sub/aud/scope + claims_digest match, jti={disclosure['jti'][-12:]}"
                if good
                else f"mismatched={mismatches} claims_digest_ok={combined_ok} jti_ok={jti_ok}")
        rep.add("C6", f"{label}: record asserts no raw token committed",
                slot.get("raw_token_committed") is False,
                "raw_token_committed=false")

    # -- C7: raw-token absence -------------------------------------------------
    if token_probe is None:
        rep.add("C7", "raw access token absent from both ledgers", False,
                "could not check — no token probe supplied "
                "(absent is never pass; this is 'could not check')")
    else:
        needles = [token_probe["token"], *token_probe["token"].split(".")]
        hits = []
        for name, text in raw_ledger_text.items():
            for n in needles:
                if len(n) >= 16 and n in text:
                    hits.append((name, n[:12] + "…"))
        rep.add("C7", "raw access token absent from both ledgers", not hits,
                f"searched {len(needles)} needles (whole token + each segment) "
                f"across {sum(len(t) for t in raw_ledger_text.values())} bytes"
                if not hits else f"FOUND: {hits}")

    return rep


# ---------------------------------------------------------------------------
# Beyond the 19 — the negotiation's own commitments (opt-in, --mandate)
# ---------------------------------------------------------------------------


def mandate_report(bundle: Path) -> list[dict]:
    """Recheck what the *negotiation* committed to, from the bundle's files.

    Deliberately **not** part of the 19 checks above, and deliberately printed
    under its own heading. The 19 are about the sealed records; these are
    about whether the sealed records agree with the separately published
    negotiation artefacts (``wicket.json``, ``negotiation.json``). Both matter,
    but a demo that quietly grows its own headline number is a demo that has
    stopped being comparable to the last one.

    Every row is a real recomputation. A missing file is reported as **could
    not check** and fails — absent is never pass.
    """
    rows: list[dict] = []

    def row(name: str, passed: bool, detail: str) -> None:
        rows.append({"name": name, "passed": bool(passed), "detail": detail})

    wicket_path, neg_path = bundle / "wicket.json", bundle / "negotiation.json"
    tx = json.loads((bundle / "transaction.json").read_text())
    mandate = tx.get("mandate")
    if mandate is None:
        row("mandate present in transaction.json", False,
            "absent — could not check (this bundle predates the negotiation acts)")
        return rows
    if not wicket_path.exists() or not neg_path.exists():
        row("wicket.json + negotiation.json published", False,
            "one or both absent — could not check")
        return rows

    wicket = json.loads(wicket_path.read_text())
    neg = json.loads(neg_path.read_text())

    # 1 — the private brief's fingerprint recomputes from the published manifest
    recomputed = jcs_digest(wicket)
    row("wicket digest recomputes from wicket.json",
        recomputed == mandate["wicket_digest"],
        f"{recomputed[:24]}… vs sealed {mandate['wicket_digest'][:24]}…")

    # 2 — the whole negotiation record's fingerprint
    neg_body = {k: v for k, v in neg.items()
                if k not in ("privacy_check", "negotiation_digest")}
    neg_digest = jcs_digest(neg_body)
    row("negotiation digest recomputes from negotiation.json",
        neg_digest == mandate["negotiation_digest"],
        f"{len(neg.get('rounds', []))} rounds, {neg_digest[:24]}…")

    # 3 — the winning offer's fingerprint
    offer_digest = jcs_digest(neg["winner"]) if neg.get("winner") else None
    row("accepted-offer digest recomputes from the winner block",
        offer_digest == mandate["accepted_offer_digest"],
        f"{neg.get('winner', {}).get('seller', '?')} "
        f"@ {neg.get('winner', {}).get('unit_price_usd', '?')}/unit")

    # 4 — both parties sealed the SAME accepted offer, from opposite sides
    buyer = read_jsonl(bundle / "buyer-ledger.jsonl")
    seller = read_jsonl(bundle / "seller-ledger.jsonl")
    order = find(buyer, "submit_order")
    recv = find(seller, "receive_order")
    sealed_buyer = (compute_attestation(order).get("mandate") or {}).get(
        "accepted_offer_digest")
    sealed_seller = compute_attestation(recv).get("accepted_offer_digest")
    row("both ledgers sealed the same accepted-offer digest",
        sealed_buyer is not None and sealed_buyer == sealed_seller == offer_digest,
        f"buyer {str(sealed_buyer)[:16]}… / seller {str(sealed_seller)[:16]}…")

    # 5 — regrade the winner against the DISCLOSED brief. This is the one that
    #     matters: it is a stranger re-running the buyer's own eligibility test
    #     rather than taking "wicket_result: pass" on trust.
    w, inv = neg.get("winner") or {}, wicket["hard_invariants"]
    regrade = []
    if w:
        from decimal import Decimal
        regrade = [
            ("quantity", w["quantity"] == inv["quantity"]),
            ("unit_ceiling",
             Decimal(w["unit_price_usd"]) <= Decimal(inv["unit_ceiling_usd"])),
            ("payment_terms", w["payment_terms"] == inv["required_payment_terms"]),
            ("lead_time", w["lead_time_days"] <= inv["max_lead_time_days"]),
        ]
    failed = [n for n, good in regrade if not good]
    row("winner regraded against the disclosed hard invariants",
        bool(regrade) and not failed and mandate["wicket_result"] == "pass",
        f"{len(regrade)} invariants rechecked, {len(failed)} failed"
        + (f": {failed}" if failed else "")
        + f"; record claims '{mandate['wicket_result']}'")

    # 6 — close the loop: the order document that hashes to the subject_digest
    #     BOTH ledgers sealed is, line by line, the offer that won. Capsules
    #     carry digests, not tool inputs, so this is the join that turns "a
    #     shared digest" into "a shared, readable deal".
    order_doc = tx.get("order") or {}
    li = (order_doc.get("line_items") or [{}])[0]
    sd_ok = jcs_digest(order_doc) == tx.get("subject_digest")
    agrees = bool(w) and (
        order_doc.get("vendor_operator") == w["seller"]
        and li.get("unit_price_usd") == w["unit_price_usd"]
        and li.get("qty") == w["quantity"]
        and order_doc.get("terms") == w["payment_terms"]
        and order_doc.get("amount_usd") == w["total_usd"])
    row("order hashing to the sealed subject_digest IS the winning offer",
        sd_ok and agrees,
        f"{order_doc.get('vendor', '?')} {li.get('qty', '?')} @ "
        f"{li.get('unit_price_usd', '?')} {order_doc.get('terms', '?')} "
        f"= {order_doc.get('amount_usd', '?')}; subject_digest recomputes={sd_ok}")

    return rows


# ---------------------------------------------------------------------------
# Loading and running
# ---------------------------------------------------------------------------


def evaluate(bundle: Path, tamper: str | None = None) -> tuple[Report, str | None]:
    """Load a bundle, optionally tamper with a copy of it, and run the checks.

    Split out of ``main`` so ``narrate.py`` can show the *same rows* the
    stand-alone tool shows — in the terminal and in the ``--html`` render —
    without running the checks twice or re-deriving them.
    """
    b = Path(bundle)
    buyer_path, seller_path = b / "buyer-ledger.jsonl", b / "seller-ledger.jsonl"
    buyer = read_jsonl(buyer_path)
    seller = read_jsonl(seller_path)
    parties = json.loads((b / "parties.json").read_text())
    disclosure = json.loads((b / "authority-disclosure.json").read_text())
    transaction = json.loads((b / "transaction.json").read_text())
    probe_path = b / "token-probe.json"
    token_probe = json.loads(probe_path.read_text()) if probe_path.exists() else None
    raw_text = {
        "buyer-ledger.jsonl": buyer_path.read_text(),
        "seller-ledger.jsonl": seller_path.read_text(),
    }

    what = None
    if tamper:
        buyer, seller = copy.deepcopy(buyer), copy.deepcopy(seller)
        disclosure = copy.deepcopy(disclosure)
        what = apply_tamper(tamper, buyer, seller, disclosure)
        raw_text = {
            "buyer-ledger.jsonl": "\n".join(json.dumps(r) for r in buyer),
            "seller-ledger.jsonl": "\n".join(json.dumps(r) for r in seller),
        }

    rep = cross_verify(buyer, seller, parties, disclosure, transaction,
                       raw_text, token_probe)
    return rep, what


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundle", required=True, type=Path)
    ap.add_argument("--tamper", default=None,
                    choices=["capsule_id", "output_digest", "cross_citation",
                             "authority_scope"])
    ap.add_argument("--quiet", action="store_true",
                    help="print only the checks that FAILED")
    ap.add_argument("--mandate", action="store_true",
                    help="ALSO recheck the negotiation's commitments (wicket digest, "
                         "negotiation digest, accepted offer). Separate section, "
                         "NOT counted in the headline check total")
    args = ap.parse_args()

    rep, what = evaluate(args.bundle, args.tamper)
    if what:
        print(f"  TAMPER [{args.tamper}]: {what}")

    print(rep.render(failures_only=args.quiet))
    failed = [r for r in rep.rows if r[2] == BAD]
    if args.tamper:
        print(f"\n  -> {len(failed)} check(s) FAILED; the tamper was detected."
              if failed else
              "\n  -> NOTHING FAILED. The tamper went undetected — that is a bug.")
        return 0 if failed else 1
    print(f"\n  -> {len(rep.rows)} checks, {len(failed)} failures. "
          f"Bundle {'VERIFIES' if rep.ok else 'DOES NOT VERIFY'}.")

    mandate_failed = []
    if args.mandate:
        print("\n  Beyond the 19 — the negotiation's own commitments:")
        for row in mandate_report(args.bundle):
            print(f"     {'ok  ' if row['passed'] else 'FAIL'} "
                  f"{row['name']:<64} {row['detail']}")
            if not row["passed"]:
                mandate_failed.append(row["name"])
    return 0 if (rep.ok and not mandate_failed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
