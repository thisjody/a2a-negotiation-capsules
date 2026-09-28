#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The negotiation front-half — two competing sellers, narrated counter-rounds.

Engagement borrowed from Steven's **accountable deal-room**
(``action-state-group/accountable-dealroom``): its DJ-hire scenario is the
most watchable thing this program has built, and four of its ideas are why —

1.  the buyer **narrates every move before it makes it**
    (``skills/dj-buyer/SKILL.md``: *"NARRATE EVERY MOVE OUT LOUD — say it
    before you do it"*);
2.  **two competing sellers** returning genuinely different offers
    (``app/sellers/marcus.py`` at $1,400/30-70/no-limbo vs
    ``app/sellers/nadia.py`` at $1,300/50-50/limbo+$75);
3.  **offer/counter rounds with a stated strategy** — anchor at 60 % of the
    quote, climb toward a target, walk if it breaks the mandate;
4.  a private **wicket**: the buyer's hidden constraints, committed as a
    digest so the deal proves the agent stayed inside its brief *without the
    ceiling ever appearing in the room*.

What is **not** borrowed is the risk. The deal-room's sellers are live agents
on a poll loop behind an HTTP service, and its buyer is an LLM working curl.
This module is **scripted and deterministic**: fixed ladders, integer rounds,
exact-decimal arithmetic, no model call, no socket, no clock. Same inputs,
same offers, same winner, same digest — every run, forever. A demo that can
hang on stage is not a demo.

The output of this module is one thing the rest of `demo2` consumes: **the
winning seller and its terms**, which become the counterparty and the order in
the existing AAuth → two-ledger → cross-verify → tamper flow.

Money is exact decimal, never float — §5.1 of the capsule spec forbids floats
in digest fields, and `capsule-emit` issue #128 reports a float tool argument
silently breaking a chain. `Decimal` in, canonical strings out.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Iterable

QUANTUM = Decimal("0.01")


def usd(amount: Decimal) -> str:
    """Canonical money string. Two places, half-up, no float anywhere."""
    return str(amount.quantize(QUANTUM, rounding=ROUND_HALF_UP))


def jcs_digest(obj) -> str:
    """SHA-256 over JCS-ish canonical JSON (sorted keys, no spaces)."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# The buyer's wicket — private constraints, never spoken in a room
# ---------------------------------------------------------------------------

# The principal (a human) approved this brief before the agent started. The
# agent negotiates inside it and never reveals it; what gets sealed into the
# order capsule is its DIGEST plus a pass/fail, so a stranger can check the
# agent obeyed a mandate without ever learning the ceiling.
#
# Written out to ``wicket.json`` in the bundle so anyone can recompute the
# digest for themselves. (Deal-room parallel: ``skills/dj-buyer/wicket.json``.)
WICKET = {
    "manifest_version": "1",
    "party": "buyer",
    "agent": "acme-co/po-agent",
    "approved_by": "dana@acme-co.example",
    "approved_at": "2026-09-01",
    "brief": "29 widgets, net30 payment terms, delivered inside two weeks.",
    "hard_invariants": {
        "quantity": 29,
        "unit_ceiling_usd": "50.00",
        "required_payment_terms": "net30",
        "max_lead_time_days": 14,
    },
    "negotiation": {
        "open_counter_pct_of_quote": 60,
        "unit_target_usd": "43.00",
        "climb_headroom_usd": "3.00",
        "counter_every_offer": True,
        "max_rounds": 3,
    },
}

WICKET_DIGEST = jcs_digest(WICKET)

# The values that must never cross the wire. Checked mechanically at the end
# of the negotiation (``privacy`` in the returned record) rather than asserted
# in prose — absent is never pass, and neither is unchecked.
WICKET_SECRETS = (
    WICKET["hard_invariants"]["unit_ceiling_usd"],
    WICKET["negotiation"]["unit_target_usd"],
)

QUANTITY = WICKET["hard_invariants"]["quantity"]
UNIT_CEILING = Decimal(WICKET["hard_invariants"]["unit_ceiling_usd"])
UNIT_TARGET = Decimal(WICKET["negotiation"]["unit_target_usd"])
CLIMB_HEADROOM = Decimal(WICKET["negotiation"]["climb_headroom_usd"])
OPEN_PCT = Decimal(WICKET["negotiation"]["open_counter_pct_of_quote"]) / Decimal(100)

# The public brief — this DOES cross the wire, to both sellers, identically.
RFQ = {
    "rfq_id": "RFQ-7777",
    "buyer": "Acme Co",
    "sku": "widget",
    "quantity": QUANTITY,
    "required_payment_terms": "net30",
    "max_lead_time_days": 14,
    "note": "Quoting two suppliers. Price per unit, payment terms, lead time.",
}


# ---------------------------------------------------------------------------
# The two sellers — different offers, different shapes, deterministic ladders
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Quote:
    """One seller position in one round. Fixed, not generated."""

    unit_price_usd: str
    payment_terms: str
    lead_time_days: int
    line: str  # what the seller says out loud
    final: bool = False

    def total_usd(self, qty: int = QUANTITY) -> str:
        return usd(Decimal(self.unit_price_usd) * qty)


@dataclass(frozen=True)
class Seller:
    operator: str
    display: str
    blurb: str
    ladder: tuple[Quote, ...]

    def quote(self, round_index: int) -> Quote:
        """A seller's position never improves past its scripted floor."""
        return self.ladder[min(round_index, len(self.ladder) - 1)]


# Frobozz Supply: opens high on price AND on terms (net15), then moves on both.
# Ends cheapest-inside-the-mandate with the shortest lead time.
FROBOZZ = Seller(
    operator="frobozz-supply",
    display="Frobozz Supply",
    blurb="Incumbent widget supplier. Regional warehouse, own freight desk.",
    ladder=(
        Quote("52.00", "net15", 12,
              "List is $52.00 a unit, net15, twelve days out. No volume break at 29."),
        Quote("47.50", "net30", 12,
              "$47.50 and I'll move you to net30 — the terms cost me less than the price does."),
        Quote("42.00", "net30", 10,
              "$42.00, net30, ten days, and I absorb the expedited freight. "
              "That is best and final.", final=True),
    ),
)

# Globex Corp: opens better on terms, worse on lead time, and ends CHEAPEST —
# but only by lengthening the lead time past the buyer's hard invariant. The
# lowest number is not the winning number, and the record says why.
GLOBEX = Seller(
    operator="globex-corp",
    display="Globex Corp",
    blurb="National distributor. Container-scale pricing, port-side lead times.",
    ladder=(
        Quote("48.00", "net30", 21,
              "$48.00 a unit, net30 from the start, but I'm three weeks out."),
        Quote("46.00", "net30", 16,
              "$46.00. I can pull it to sixteen days; below that I'd be paying air freight."),
        Quote("41.50", "net30", 21,
              "$41.50 — I'll beat anyone on price if you can take the three-week lead. "
              "That's the trade.", final=True),
    ),
)

SELLERS: tuple[Seller, ...] = (FROBOZZ, GLOBEX)


# ---------------------------------------------------------------------------
# The wicket check — the only thing that decides eligibility
# ---------------------------------------------------------------------------


def wicket_check(quote: Quote) -> tuple[bool, list[dict]]:
    """Grade a final offer against the hard invariants.

    Returns ``(eligible, checks)``. Every invariant is reported with its own
    outcome, pass or fail — a seller that is knocked out shows *which* line
    knocked it out, which is the point of having a mandate at all.
    """
    checks = [
        {
            "invariant": "unit_ceiling",
            "passed": Decimal(quote.unit_price_usd) <= UNIT_CEILING,
            "detail": f"unit {quote.unit_price_usd} vs ceiling (private)",
        },
        {
            "invariant": "payment_terms",
            "passed": quote.payment_terms == WICKET["hard_invariants"]["required_payment_terms"],
            "detail": f"terms {quote.payment_terms}, brief requires "
                      f"{WICKET['hard_invariants']['required_payment_terms']}",
        },
        {
            "invariant": "lead_time",
            "passed": quote.lead_time_days <= WICKET["hard_invariants"]["max_lead_time_days"],
            "detail": f"lead {quote.lead_time_days}d vs "
                      f"{WICKET['hard_invariants']['max_lead_time_days']}d maximum",
        },
    ]
    return all(c["passed"] for c in checks), checks


# ---------------------------------------------------------------------------
# The negotiation itself
# ---------------------------------------------------------------------------

Say = Callable[..., None]


def run(*, wire, say: Say, act: Callable[[str], None],
        sellers: Iterable[Seller] = SELLERS) -> dict:
    """Play the scripted negotiation, narrating every move before making it.

    ``say(kind, text)`` and ``act(title)`` are supplied by the narrator: ``say``
    prints one narrated line and holds a beat, ``act`` opens a new act. ``say``
    is what makes a watcher read the reasoning *before* the action lands.
    ``wire`` records the frames that would have crossed a transport, so the
    negotiation ends up in the evidence bundle's ``wire.json`` alongside
    everything else.

    Returns the negotiation record: rounds, offers, the wicket grading, the
    winner and the resulting order. That record is digested and the digest is
    sealed into the buyer's ``submit_order`` capsule, so the sealed order
    commits to the exact negotiation that produced it.
    """
    sellers = tuple(sellers)
    rounds: list[dict] = []

    # -- the mandate, shown to the room and to nobody else ------------------
    act("The brief, the wicket, and two competing suppliers")
    say("think", "Before I opened a single conversation, a human approved what I am "
                 "allowed to agree to. That brief is my wicket. The room sees it "
                 "here because you are the audience; no supplier ever will.")
    hi, ng = WICKET["hard_invariants"], WICKET["negotiation"]
    say("note", f"wicket  hard    {hi['quantity']} units - "
                f"ceiling {hi['unit_ceiling_usd']}/unit - "
                f"{hi['required_payment_terms']} - "
                f"lead <= {hi['max_lead_time_days']}d", beat=0.4)
    say("note", f"wicket  aim     open at {ng['open_counter_pct_of_quote']}% of quote, "
                f"climb toward {ng['unit_target_usd']}/unit, "
                f"max {ng['max_rounds']} rounds", beat=0.4)
    say("note", f"wicket  digest  {WICKET_DIGEST}")
    say("think", "That digest is what gets sealed into the purchase order — not the "
                 "ceiling, not the target. A stranger can later prove I stayed inside "
                 "a mandate without ever learning what my ceiling was.")
    for s in sellers:
        say("note", f"seller  {s.display:<16} {s.blurb}", beat=0.4)

    # -- round 1: the brief goes out, both sellers quote --------------------
    say("think", "One brief, two suppliers, same wording to both — if the "
                 "quotes differ, it is the sellers that differ, not the ask.")
    wire.send("acme-co/po-agent", ", ".join(s.operator for s in sellers),
              "rfq.broadcast", RFQ)
    say("out", f"To {' and '.join(s.display for s in sellers)}: "
               f"RFQ-7777 — {QUANTITY} x widget, net30, delivered inside 14 days. "
               f"Quote me.")

    r1_offers = []
    for s in sellers:
        q = s.quote(0)
        wire.send(s.operator, "acme-co/po-agent", "rfq.quote", _frame(s, q))
        say("in", f"{s.display}: {_terms_line(q)}")
        say("said", f'"{q.line}"', beat=0.6)
        r1_offers.append(_offer(s, q, round_no=1, counter=None))
    rounds.append({"round": 1, "kind": "opening quotes", "counter_usd": None,
                   "offers": r1_offers})

    cheapest = min(r1_offers, key=lambda o: Decimal(o["unit_price_usd"]))
    say("think", f"{cheapest['seller_display']} is the cheaper opener at "
                 f"{cheapest['unit_price_usd']} but is {cheapest['lead_time_days']} days out, "
                 f"which is outside the brief. Neither opener is close to where "
                 f"I am told to land. I counter both — every offer gets a counter.")

    # -- round 2: anchor low, at 60 % of each seller's OWN number -----------
    act("Counter-rounds — anchor low, then climb toward the target")
    say("think", "Anchoring at 60% of each seller's own quote. Not an insult — "
                 "a probe: how far a supplier moves off its opener tells me where "
                 "its floor actually is.")
    r2_offers = []
    for prev in r1_offers:
        s = _seller_by_operator(sellers, prev["seller"])
        anchor = usd(Decimal(prev["unit_price_usd"]) * OPEN_PCT)
        wire.send("acme-co/po-agent", s.operator, "rfq.counter",
                  {"rfq_id": RFQ["rfq_id"], "round": 2, "unit_price_usd": anchor,
                   "required_payment_terms": "net30", "max_lead_time_days": 14})
        say("out", f"To {s.display}: countering at {anchor}/unit "
                   f"(60% of their {prev['unit_price_usd']}) to anchor low.")
        q = s.quote(1)
        wire.send(s.operator, "acme-co/po-agent", "rfq.quote", _frame(s, q))
        moved = usd(Decimal(prev["unit_price_usd"]) - Decimal(q.unit_price_usd))
        say("in", f"{s.display}: {_terms_line(q)}   (moved {moved}/unit)")
        say("said", f'"{q.line}"', beat=0.6)
        r2_offers.append(_offer(s, q, round_no=2, counter=anchor, moved_usd=moved))
    rounds.append({"round": 2, "kind": "buyer anchors at 60%",
                   "counter_usd": None, "offers": r2_offers})

    movers = sorted(r2_offers, key=lambda o: Decimal(o["moved_usd"]), reverse=True)
    say("think", f"{movers[0]['seller_display']} moved {movers[0]['moved_usd']} a unit off "
                 f"its opener; {movers[-1]['seller_display']} moved {movers[-1]['moved_usd']}. "
                 f"The one that moved further has further left to move. "
                 f"One more round, then I stop.")

    # -- round 3: climb toward the target, same number to both -------------
    climb = usd(UNIT_TARGET - CLIMB_HEADROOM)
    say("think", f"Climbing to {climb}/unit with both — deliberately short of where "
                 f"I am told to land, so I still have a move in hand. Same number to "
                 f"each, and each of them knows there is another quote on my desk.")
    r3_offers = []
    for prev in r2_offers:
        s = _seller_by_operator(sellers, prev["seller"])
        wire.send("acme-co/po-agent", s.operator, "rfq.counter",
                  {"rfq_id": RFQ["rfq_id"], "round": 3, "unit_price_usd": climb,
                   "required_payment_terms": "net30", "max_lead_time_days": 14,
                   "note": "I am holding a competing quote."})
        say("out", f"To {s.display}: {climb}/unit, net30, inside 14 days. "
                   f"I am comparing you against another quote.")
        q = s.quote(2)
        wire.send(s.operator, "acme-co/po-agent", "rfq.quote", _frame(s, q))
        tag = "   [best and final]" if q.final else ""
        say("in", f"{s.display}: {_terms_line(q)}{tag}")
        say("said", f'"{q.line}"', beat=0.6)
        r3_offers.append(_offer(s, q, round_no=3, counter=climb,
                                moved_usd=usd(Decimal(prev["unit_price_usd"])
                                              - Decimal(q.unit_price_usd))))
    rounds.append({"round": 3, "kind": "buyer climbs, sellers close",
                   "counter_usd": climb, "offers": r3_offers})

    # -- the wicket check, then the pick -----------------------------------
    act("The wicket check, and the pick")
    say("think", "Both are done moving. Now the part that is not haggling: "
                 "does each final offer fit the brief my principal approved? "
                 "That brief is private — the grading is not.")

    graded = []
    for o in r3_offers:
        s = _seller_by_operator(sellers, o["seller"])
        q = s.quote(2)
        eligible, checks = wicket_check(q)
        graded.append({**o, "eligible": eligible, "wicket_checks": checks})

    for g in graded:
        verdict = "ELIGIBLE" if g["eligible"] else "OUT"
        failed = [c["invariant"] for c in g["wicket_checks"] if not c["passed"]]
        say("note", f"wicket  {g['seller_display']:<16} {verdict}"
                    + (f" — fails {', '.join(failed)}" if failed else ""))

    eligible = [g for g in graded if g["eligible"]]
    rejected = [g for g in graded if not g["eligible"]]
    cheapest_overall = min(graded, key=lambda g: Decimal(g["unit_price_usd"]))

    if not eligible:
        # The scripted ladders never reach here, but the branch is real: a
        # buyer with no eligible offer walks, and says so.
        say("think", "No offer fits the brief. I do not have discretion to "
                     "stretch a hard invariant, so I walk — documented, no deal.")
        return _record(rounds, graded, winner=None, privacy=_privacy(wire))

    winner = min(eligible, key=lambda g: Decimal(g["unit_price_usd"]))

    if cheapest_overall is not winner:
        gap = usd((Decimal(winner["unit_price_usd"])
                   - Decimal(cheapest_overall["unit_price_usd"])) * QUANTITY)
        say("think", f"{cheapest_overall['seller_display']} is the cheapest number on the "
                     f"table — {gap} cheaper across the order. It is also outside a hard "
                     f"invariant, and a hard invariant is not mine to trade. "
                     f"The lowest price is not the winning price.")

    beats_target = Decimal(winner["unit_price_usd"]) <= UNIT_TARGET
    say("think", f"{winner['seller_display']} at {winner['unit_price_usd']}/unit clears every "
                 f"invariant and {'beats' if beats_target else 'is short of'} the number I was "
                 f"told to land on. Over-negotiating a winning offer is how you lose it. "
                 f"I stop here.")
    wire.send("acme-co/po-agent", winner["seller"], "rfq.select",
              {"rfq_id": RFQ["rfq_id"], "selected": winner["seller"],
               "unit_price_usd": winner["unit_price_usd"],
               "payment_terms": winner["payment_terms"],
               "lead_time_days": winner["lead_time_days"],
               "wicket_digest": WICKET_DIGEST, "wicket_result": "pass"})
    say("out", f"To {winner['seller_display']}: selected. "
               f"{QUANTITY} units at {winner['unit_price_usd']}, "
               f"{winner['payment_terms']}, {winner['lead_time_days']} days — "
               f"{winner['total_usd']} total. Raising the PO.")
    for g in rejected:
        s_op = g["seller"]
        wire.send("acme-co/po-agent", s_op, "rfq.decline",
                  {"rfq_id": RFQ["rfq_id"], "outcome": "not selected",
                   "reason_code": "buyer_hard_invariant",
                   "note": "constraint in the buyer's approved brief; "
                           "the brief itself is not disclosed"})
        say("out", f"To {g['seller_display']}: not this time — a constraint in my "
                   f"brief, not your price. I am not telling them which one.")

    return _record(rounds, graded, winner=winner, privacy=_privacy(wire))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _terms_line(q: Quote) -> str:
    return (f"{q.unit_price_usd}/unit  {q.payment_terms}  {q.lead_time_days}d lead   "
            f"({q.total_usd()} total)")


def _frame(s: Seller, q: Quote) -> dict:
    return {"rfq_id": RFQ["rfq_id"], "seller": s.operator,
            "unit_price_usd": q.unit_price_usd, "payment_terms": q.payment_terms,
            "lead_time_days": q.lead_time_days, "quantity": QUANTITY,
            "total_usd": q.total_usd()}


def _offer(s: Seller, q: Quote, *, round_no: int, counter: str | None,
           moved_usd: str = "0.00") -> dict:
    return {
        "round": round_no,
        "seller": s.operator,
        "seller_display": s.display,
        "buyer_counter_usd": counter,
        "unit_price_usd": q.unit_price_usd,
        "payment_terms": q.payment_terms,
        "lead_time_days": q.lead_time_days,
        "total_usd": q.total_usd(),
        "said": q.line,
        "moved_usd": moved_usd,
        "final": q.final,
    }


def _seller_by_operator(sellers: tuple[Seller, ...], operator: str) -> Seller:
    for s in sellers:
        if s.operator == operator:
            return s
    raise KeyError(operator)


def _privacy(wire) -> dict:
    """Mechanically check the wicket's private numbers never crossed the wire.

    The claim "the ceiling never appears in a room" is exactly the sort of
    thing a demo asserts and never checks. This checks it: every frame is
    serialised and searched for each secret string.
    """
    blob = json.dumps(wire.as_json(), sort_keys=True)
    hits = [s for s in WICKET_SECRETS if s in blob]
    return {
        "frames_searched": len(wire.frames),
        "secrets_searched": list(WICKET_SECRETS),
        "leaked": hits,
        "passed": not hits,
    }


def _record(rounds: list[dict], graded: list[dict], *, winner: dict | None,
            privacy: dict) -> dict:
    """The negotiation record. Deterministic — its digest is stable per build."""
    rec: dict = {
        "rfq": RFQ,
        "sellers": [{"operator": s.operator, "display": s.display, "blurb": s.blurb}
                    for s in SELLERS],
        "rounds": rounds,
        "final": [{k: g[k] for k in ("seller", "seller_display", "unit_price_usd",
                                     "payment_terms", "lead_time_days", "total_usd",
                                     "eligible", "wicket_checks")}
                  for g in graded],
        "wicket_digest": WICKET_DIGEST,
        "wicket_result": "pass" if winner else "no_eligible_offer",
        "winner": None,
        "privacy_check": privacy,
    }
    if winner:
        rec["winner"] = {
            "seller": winner["seller"],
            "seller_display": winner["seller_display"],
            "unit_price_usd": winner["unit_price_usd"],
            "payment_terms": winner["payment_terms"],
            "lead_time_days": winner["lead_time_days"],
            "quantity": QUANTITY,
            "total_usd": winner["total_usd"],
        }
    # The digest deliberately excludes the privacy check, which counts wire
    # frames and therefore depends on what else the run happened to send.
    rec["negotiation_digest"] = jcs_digest(
        {k: v for k, v in rec.items() if k != "privacy_check"})
    return rec


def order_from_winner(winner: dict) -> dict:
    """The purchase order the negotiation produced.

    This is the hand-off: everything downstream — the AAuth scope, the
    subject_digest, both ledgers, the cross-verify — is about *this* dict, and
    this dict came out of the haggle rather than out of a constant.
    """
    return {
        "po_number": "PO-7777",
        "vendor": winner["seller_display"],
        "vendor_operator": winner["seller"],
        "buyer": "Acme Co",
        "line_items": [{"sku": "widget", "qty": winner["quantity"],
                        "unit_price_usd": winner["unit_price_usd"]}],
        "amount_usd": winner["total_usd"],
        "currency": "USD",
        "terms": winner["payment_terms"],
    }
