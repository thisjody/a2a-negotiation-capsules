#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sell side — Frobozz Supply's fulfilment agent. A separate counterparty.

New for demo2. Everything about this agent is its own:

* its own **operator identity** (``frobozz-supply``) on every capsule,
* its own **ledger file**, never shared with the buyer,
* its own **Ed25519 producer key** (``capsule-emit`` auto-generates one next
  to each ledger, so the two parties' ``key_id`` values genuinely differ),
* its own **resource-server identity** for AAuth audience enforcement.

Three beats, sealed as its own capsule chain::

    receive_order  -> validates the presented AAuth token, seals what it checked
      -> fulfill    -> the work
      -> confirm    -> effect.status="confirmed", chained to the BUYER's
                       order capsule by content address

The authority story on this side is the honest one. The seller was not issued
the grant; it was *shown* one. So its capsules carry, by digest, the claims of
the grant it was shown and the result of each check it ran against it —
``presented_authority``. Its own ``disposition.authority`` is its own
operator-side authorization reference.
"""
from __future__ import annotations

from typing import Any

from capsule_emit.adapters.mcp import MCPCapsuleEmitter

from aauth import (
    AAuthError,
    ResourceServer,
    authority_commitment,
    jcs_digest,
    read_claims_unverified,
)

AAUTH_SPEC_REF = "draft-rosenberg-oauth-aauth-01 §4"


class SellerAgent:
    """Frobozz Supply's fulfilment agent."""

    default_operator = "frobozz-supply"
    developer = "fulfillment-agent@v1"

    def __init__(self, ledger: str, wire, resource_server: ResourceServer, *,
                 operator: str | None = None, display: str | None = None) -> None:
        # ``operator`` is supplied by the narrator from the *winner of the
        # negotiation* — the front-half picks the counterparty, and that
        # choice is what stamps the operator name onto every capsule this
        # agent seals. It is not a constant any more.
        self.operator = operator or self.default_operator
        self.display = display or self.operator
        self.ledger = ledger
        self.wire = wire
        self.rs = resource_server
        self.emitter = MCPCapsuleEmitter(
            operator=self.operator,
            developer=self.developer,
            ledger=ledger,
            anchor=False,
            model={"provider": "anthropic", "model_id": "claude-opus-4-8"},
        )
        self._presented: dict | None = None
        self._bilateral: dict | None = None

    def _who(self, **extra: Any) -> dict:
        slot: dict[str, Any] = {"runtime": "mcp"}
        if self._bilateral is not None:
            slot["bilateral"] = dict(self._bilateral)
        if self._presented is not None:
            slot["presented_authority"] = self._presented
        slot.update(extra)
        return slot

    def set_bilateral(self, slot: dict | None) -> None:
        """Attach the current four-move handshake state to subsequent seals.

        The values are signature *digests* and a state name from
        ``capsule_emit.bilateral`` — never a private key, never a raw
        signature over anything but the protocol's own canonical payloads.
        """
        self._bilateral = slot

    # -- beat 1: receive the order, check the token it arrived with ----------

    def receive_order(
        self,
        *,
        order: dict,
        subject_digest: str,
        buyer_order_capsule_id: str,
        buyer_operator: str,
        buyer_key_id: str,
        presented_token: str,
        issuer_jwks: dict,
        required_scope: str,
        now: int,
        accepted_offer_digest: str | None = None,
    ) -> tuple[str, list[dict]]:
        """Validate the presented AAuth token, then seal what was checked.

        Returns ``(capsule_id, checks)``. The token itself is validated here
        and then dropped — only its claim digests and the check outcomes are
        sealed. A failed check raises before any capsule claims a pass:
        **absent is never pass, and neither is unchecked.**
        """
        try:
            claims, checks = self.rs.validate_presented_token(
                presented_token,
                issuer_jwks=issuer_jwks,
                required_scope=required_scope,
                now=now,
            )
        except AAuthError:
            # A real deployment seals a blocked capsule here. The demo's
            # denial beat lives on the buy side, so this path re-raises rather
            # than inventing a second refusal story.
            raise

        commitment = authority_commitment(claims, spec_ref=AAUTH_SPEC_REF)
        self._presented = {
            **commitment,
            "presented_by": buyer_operator,
            "checks": checks,
            "checked_against_rs": self.rs.rs_id,
        }

        received = {
            "po_number": order["po_number"],
            "line_items": order["line_items"],
            "amount_usd": order["amount_usd"],
            "accepted": True,
        }
        res = self.emitter.emit_capsule(
            "receive_order",
            tool_input={"order": order, "buyer_capsule_id": buyer_order_capsule_id},
            tool_output=received,
            verdict="executed",
            effect={"type": "receive_order", "status": "dispatched"},
            action_type="decide",
            relation=None,
            extra_compute=self._who(
                subject_digest=subject_digest,
                role="responder",
                counterparty_operator=buyer_operator,
                counterparty_key_id=buyer_key_id,
                counterparty_capsule_id=buyer_order_capsule_id,
                # The offer this side actually won, by digest. The seller saw
                # only its own room, so it commits to the accepted OFFER — not
                # to the buyer's whole negotiation record, which contains a
                # competitor's numbers it never saw.
                **({"accepted_offer_digest": accepted_offer_digest}
                   if accepted_offer_digest else {}),
            ),
        )
        self.wire.send(
            self.operator, buyer_operator, "order.accepted",
            {"po_number": order["po_number"], "seller_capsule_id": res.capsule_id,
             "auth_checks": [{k: c[k] for k in ("check", "passed")} for c in checks]},
        )
        return res.capsule_id, checks

    # -- beat 2: do the work -------------------------------------------------

    def fulfill(self, *, order: dict, prior_capsule_id: str, subject_digest: str) -> tuple[dict, str]:
        fulfilment = {
            "po_number": order["po_number"],
            "shipped_units": order["line_items"][0]["qty"],
            "carrier": "Gnusto Freight",
            "tracking_ref": f"GF-{order['po_number'][-4:]}-1",
        }
        res = self.emitter.emit_capsule(
            "fulfill_order",
            tool_input={"po_number": order["po_number"]},
            tool_output=fulfilment,
            verdict="executed",
            effect={"type": "fulfill_order", "status": "dispatched"},
            action_type="decide",
            prior_capsule_id=prior_capsule_id,
            relation="confirms",
            extra_compute=self._who(subject_digest=subject_digest, role="responder"),
        )
        return fulfilment, res.capsule_id

    # -- beat 3: confirm, citing the BUYER's order capsule ------------------

    def confirm(
        self,
        *,
        order: dict,
        fulfilment: dict,
        buyer_order_capsule_id: str,
        buyer_operator: str,
        buyer_key_id: str,
        subject_digest: str,
    ) -> tuple[dict, str, str]:
        """Seal the confirmation, chained to the buyer's order capsule.

        ``prior_capsule_id`` names a capsule in the *buyer's* ledger. The
        seller cannot forge it: the id is a digest over the buyer's content,
        and the buyer's capsule is signed under the buyer's key.

        Returns ``(confirmation, capsule_id, response_digest)``.
        """
        confirmation = {
            "po_number": order["po_number"],
            "fulfillment_ref": fulfilment["tracking_ref"],
            "amount_usd": order["amount_usd"],
            "status": "fulfilled",
        }
        response_digest = jcs_digest(confirmation)
        res = self.emitter.emit_capsule(
            "confirm_fulfillment",
            tool_input={"po_number": order["po_number"],
                        "buyer_order_capsule_id": buyer_order_capsule_id},
            tool_output=confirmation,
            verdict="executed",
            effect={
                "type": "confirm_fulfillment",
                "status": "confirmed",
                "response_digest": response_digest,
            },
            action_type="decide",
            prior_capsule_id=buyer_order_capsule_id,
            relation="confirms",
            extra_compute=self._who(
                subject_digest=subject_digest,
                role="responder",
                counterparty_operator=buyer_operator,
                counterparty_key_id=buyer_key_id,
                counterparty_capsule_id=buyer_order_capsule_id,
            ),
        )
        self.wire.send(
            self.operator, buyer_operator, "fulfillment.confirm",
            {"confirmation": confirmation, "seller_capsule_id": res.capsule_id,
             "response_digest": response_digest,
             "cites_buyer_capsule_id": buyer_order_capsule_id},
        )
        return confirmation, res.capsule_id, response_digest


def claims_seen_on_wire(token: str) -> dict:
    """What the seller can read off a presented token before checking anything.

    Same discipline as the partner testbed's unverified-claims decode: base64
    only, no signature trust. Used for display; the sealed record uses the
    claims returned by the *validated* path.
    """
    return read_claims_unverified(token)
