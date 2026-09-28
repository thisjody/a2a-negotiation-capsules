#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Buy side — Acme Co's purchase-order agent, sealing to its OWN ledger.

Beats 1-4 are the existing ``examples/goose-capsule`` purchase-order story,
kept as-is because it already carries a genuine refusal:

    get_price (fyi, unchained)
      -> submit_order PO-7777 $1,240.19          effect dispatched   [chain head]
      -> approve_large_order PO-7778 $125,000.00 HITL DENIAL, blocked/planned
      -> escalate_to_manager                     executed, relation="escalates"

Beat 5 is new for demo2: a **close-out** that chains to the *seller's* confirm
capsule, which lives in a different ledger under a different operator identity
and a different signing key. That link is the buy-side half of the bilateral
cross-verify.

Money is carried as exact decimal strings, never floats — §5.1 of the capsule
spec forbids floats in digest fields, and capsule-emit issue #128 reports a
float tool argument silently breaking a chain on an earlier release. Strings
sidestep the whole question.
"""
from __future__ import annotations

from typing import Any

from capsule_emit.adapters.mcp import MCPCapsuleEmitter

from aauth import authority_commitment, authority_reference

AAUTH_SPEC_REF = "draft-rosenberg-oauth-aauth-01 §4"


class BuyerAgent:
    """Acme Co's PO agent. One operator identity, one ledger, one signing key."""

    operator = "acme-co"
    developer = "goose-agent@v1"

    def __init__(self, ledger: str, wire, *, model: dict | None = None) -> None:
        self.ledger = ledger
        self.wire = wire
        self.emitter = MCPCapsuleEmitter(
            operator=self.operator,
            developer=self.developer,
            ledger=ledger,
            anchor=False,          # no anchor submission
            model=model or {"provider": "anthropic", "model_id": "claude-opus-4-8"},
        )
        self._authority: dict | None = None
        self._authority_ref: str | None = None
        self._bilateral: dict | None = None

    # -- AAuth ---------------------------------------------------------------

    def hold_grant(self, claims: dict) -> dict:
        """Take custody of the AAuth token's *claims commitment*.

        The agent holds the raw token elsewhere (to present on the wire). What
        it hands the capsule layer is the digest-only slot — see
        ``aauth.authority_commitment``.
        """
        self._authority = authority_commitment(claims, spec_ref=AAUTH_SPEC_REF)
        self._authority_ref = authority_reference(claims)
        return self._authority

    def _who(self, **extra: Any) -> dict:
        """The who/authority slot every capsule from this agent carries."""
        slot: dict[str, Any] = {"runtime": "mcp"}
        if self._bilateral is not None:
            slot["bilateral"] = dict(self._bilateral)
        if self._authority is not None:
            slot["authority"] = self._authority
        slot.update(extra)
        return slot

    def set_bilateral(self, slot: dict | None) -> None:
        """Attach the current four-move handshake state to subsequent seals.

        The values are signature *digests* and a state name from
        ``capsule_emit.bilateral`` — never a private key, never a raw
        signature over anything but the protocol's own canonical payloads.
        """
        self._bilateral = slot

    # -- beat 1: read-only lookup -------------------------------------------

    def get_price(self, vendor: str, item: str) -> tuple[dict, str]:
        prices = {"widget": "42.00", "gadget": "128.50", "doohickey": "9.99"}
        out = {
            "vendor": vendor,
            "item": item,
            "unit_price_usd": prices.get(item.lower(), "0.00"),
            "currency": "USD",
        }
        res = self.emitter.emit_capsule(
            "get_price",
            tool_input={"vendor": vendor, "item": item},
            tool_output=out,
            action_type="fyi",
            effect={"type": "get_price", "status": "planned"},
            relation=None,
            extra_compute=self._who(),
        )
        return out, res.capsule_id

    # -- beat 2: the consequential order (the one the seller fulfills) ------

    def submit_order(self, order: dict, subject_digest: str, *,
                     mandate: dict | None = None) -> tuple[dict, str]:
        """Seal the order the seller will act on.

        ``subject_digest`` is SHA-256(JCS(order)) — the *shared* value both
        parties commit to. Its being identical on both ledgers is what lets a
        stranger say the two records are about one transaction.

        ``mandate`` carries the negotiation's commitments: the digest of the
        buyer's private wicket plus its pass/fail, the digest of the whole
        negotiation record, and the digest of the offer that won. All four are
        *digests* — the ceiling and the target never enter the capsule, only
        proof that a mandate existed and this order was inside it. (The idea
        is the deal-room's `wicket_digest` + `wicket_result` §8.1 policy
        record; see `negotiate.py`.) They ride in `compute_attestation`, so
        `capsule_id` covers them and the producer signature covers that —
        editing any of them breaks C1 and C2 like any other content.
        """
        counterparty = order.get("vendor_operator", "frobozz-supply")
        out = {
            "status": "dispatched",
            "po_number": order["po_number"],
            "vendor": order["vendor"],
            "amount_usd": order["amount_usd"],
            "confirmation_ref": f"CONF-{order['po_number'][-4:]}",
        }
        res = self.emitter.emit_capsule(
            "submit_order",
            tool_input=order,
            tool_output=out,
            verdict="executed",
            effect={"type": "write_order", "status": "dispatched"},
            action_type="decide",
            relation=None,
            extra_compute=self._who(
                subject_digest=subject_digest,
                role="requester",
                counterparty_operator=counterparty,
                **({"mandate": mandate} if mandate else {}),
            ),
        )
        self.wire.send(
            self.operator, counterparty, "order.submit",
            {"order": order, "subject_digest": subject_digest,
             "buyer_capsule_id": res.capsule_id},
        )
        return out, res.capsule_id

    # -- beat 3: the HITL denial (kept verbatim from goose-capsule) ----------

    def hitl_denial(self, request: dict, outcome: dict, prior_capsule_id: str) -> str:
        """A human already refused this; the capsule records the refusal.

        Nothing prompts at runtime — the approval request and outcome are
        fixed inputs. Narrate it as "the record of a denial a human made",
        never as "watch the human reject it."

        ``relation=None``: this refusal chains to the dispatch it denies
        without asserting "confirms", which is wrong in both directions — a
        human denial is a terminal resolution, not a confirmation. Same ruling
        as ``examples/goose-capsule``.

        **Observed, capsule-emit 0.7.0:** ``relation=None`` does not omit the
        relation; the emitter writes ``chain.relation="sequence"``. The
        spec's §5.4.4 requires a relation whenever a chain block is present,
        so there is nowhere for "no assertion" to live in the record. Narrate
        it as "sequence", not as "unlabelled" — and if a resolution-class
        relation (``resolves``/``refuses``) is wanted, that is a draft change,
        not a demo change.
        """
        res = self.emitter.emit_capsule(
            "approve_large_order",
            tool_input=request,
            tool_output=outcome,
            verdict="blocked",
            effect={"type": "approve_large_order", "status": "planned"},
            action_type="decide",
            human_disposed=True,
            approver="human",
            decision="reject",
            prior_capsule_id=prior_capsule_id,
            relation=None,
            extra_compute=self._who(approver_id=outcome["approver_id"]),
        )
        assert res.capsule["disposition"]["verdict_class"] == "blocked"
        assert res.capsule["effect"]["status"] == "planned"
        return res.capsule_id

    # -- beat 4: escalation past the denial ---------------------------------

    def escalate(self, payload: dict, result: dict, prior_capsule_id: str) -> str:
        res = self.emitter.emit_capsule(
            "escalate_to_manager",
            tool_input=payload,
            tool_output=result,
            verdict="executed",
            effect={"type": "escalate_to_manager", "status": "dispatched"},
            action_type="fyi",
            prior_capsule_id=prior_capsule_id,
            relation="escalates",
            extra_compute=self._who(),
        )
        return res.capsule_id

    # -- beat 5: close-out citing the SELLER's confirm capsule --------------

    def close_out(
        self,
        *,
        seller_confirm_capsule_id: str,
        seller_operator: str,
        seller_key_id: str,
        subject_digest: str,
        confirmation: dict,
        response_digest: str,
    ) -> str:
        """Close the transaction by citing the counterparty's record.

        ``prior_capsule_id`` is a capsule in the *seller's* ledger. That is
        deliberate: this ledger alone cannot resolve the link, and the union
        of the two can. See ``crossverify.py`` checks C4/C5.
        """
        out = {
            "po_number": confirmation["po_number"],
            "closed": True,
            "counterparty_confirmation_ref": confirmation["fulfillment_ref"],
        }
        res = self.emitter.emit_capsule(
            "close_out_order",
            tool_input={"po_number": confirmation["po_number"],
                        "seller_confirm_capsule_id": seller_confirm_capsule_id},
            tool_output=out,
            verdict="executed",
            effect={
                "type": "close_out_order",
                "status": "confirmed",
                "response_digest": response_digest,
            },
            action_type="decide",
            prior_capsule_id=seller_confirm_capsule_id,
            relation="confirms",
            extra_compute=self._who(
                subject_digest=subject_digest,
                role="requester",
                counterparty_operator=seller_operator,
                counterparty_key_id=seller_key_id,
                counterparty_capsule_id=seller_confirm_capsule_id,
            ),
        )
        return res.capsule_id
