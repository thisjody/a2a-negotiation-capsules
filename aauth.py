#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""AAuth seam for demo2 — the "may" half of the Sep-4 A2A demo.

Models the Agent Authorization Grant of
**draft-rosenberg-oauth-aauth-01** ("AAuth - Agentic Authorization OAuth 2.1
Extension", J. Rosenberg / P. White, 19 October 2025), read from the staged
copy of the draft. Section numbers below are that draft's.

What is modelled, and from where
--------------------------------
* **§2 Framework.** User -> AI Agent -> Authorization Server (AS), with a
  Resource Server (RS) the agent needs a token for, and a live (human) agent
  who can approve higher-privilege operations.
* **§3.1 Basic Token Flow.** The agent collects a set of PII elements over a
  channel that cannot carry a browser redirect, hands them to the AS, and the
  AS maps the tuple to a user. The security argument is the *sparseness* of
  the PII-tuple -> user mapping.  This module carries only the **names** of the
  PII elements collected and a pre-agreed subject handle — never PII values.
  A real AS does the mapping; here it is a dict lookup, clearly labelled.
* **§3.2 Human-In-The-Loop.** The AS — not the agent — initiates the consent
  review, *displays the reason and each scope_descriptions entry*,
  authenticates the user, and binds approval to the ``request_code``. The
  agent "does not handle redirects or UI rendering — it passively awaits
  token availability" and then polls.
* **§4 Detailed OAuth Grant Flow.**
  - ``POST /agent_authorization`` with
    ``grant_type=urn:ietf:params:oauth:grant-type:agent_authorization``,
    space-delimited ``scope``, and a human-readable ``reason`` that the AS
    **MUST echo verbatim**.
  - The AS fetches each scope's description from the target RS's
    ``https://{rs}/.well-known/aauth.json#scope_descriptions``.
  - The AS returns ``{request_code, token_endpoint, poll_interval,
    expires_in, ...}``.
  - The agent then polls ``POST /token`` with
    ``grant_type=urn:ietf:params:oauth:grant-type:device_code`` and
    ``device_code=<request_code>``; pending is
    ``{"error":"authorization_pending"}``; success is a standard OAuth 2.x
    token response with
    ``issued_token_type=urn:ietf:params:oauth:token-type:jwt``.

Honest limits (say these out loud in the room)
----------------------------------------------
1. **This AS is a stub that runs in this process.** It holds a freshly
   generated Ed25519 key and mints a *real, verifiable* compact JWS — so the
   seller's audience/scope/expiry/signature checks are real checks against a
   real signature. What they do **not** prove is that any deployed identity
   provider issued anything. Swapping in a live IdP is a config change
   (issuer URL + JWKS URL + client credentials); nothing in the capsule layer
   moves.
2. **§4 of the draft says "Details to be filled in."** The token's *claim set*
   is not normatively specified there. The claims used here (``iss sub aud
   scope jti iat exp client_id``) are ordinary OAuth 2.1 / RFC 9068-shaped
   choices, not draft-mandated ones. Labelled as such wherever it matters.
3. **No PII values ever enter this module**, so the §3.1 hallucination
   argument is *described*, not exercised. The AS's PII->user map is a dict.

The capsule contract (the reason this file exists)
--------------------------------------------------
``authority_commitment()`` turns a claim set into a **digest-only** slot for
a capsule's who/authority position. The raw token string never enters a
capsule, a ledger, or a printed wire frame. ``crossverify.py`` re-derives the
digests from a separately disclosed claim set and additionally greps both
ledgers for the raw token to prove its absence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# ── draft-rosenberg-oauth-aauth-01 §4 identifiers ──────────────────────────
AGENT_AUTHORIZATION_GRANT = "urn:ietf:params:oauth:grant-type:agent_authorization"
DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
ISSUED_TOKEN_TYPE_JWT = "urn:ietf:params:oauth:token-type:jwt"
AUTHORIZATION_PENDING = {"error": "authorization_pending"}


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64u_json(obj: Any) -> str:
    return _b64u(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())


def jcs_digest(obj: Any) -> str:
    """SHA-256 over deterministic JSON (sorted keys, compact separators).

    Same canonicalization the capsule layer uses (``canonicalization_id:
    jcs``), so a verifier needs one rule, not two.
    """
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class AAuthError(Exception):
    """Raised where a real AS/RS would return an OAuth error response."""


# ---------------------------------------------------------------------------
# Resource Server side — §4 step 2's scope_descriptions source
# ---------------------------------------------------------------------------


@dataclass
class ResourceServer:
    """The RS the buyer agent needs a token *for* — here, the seller's API.

    Publishes ``/.well-known/aauth.json#scope_descriptions`` (§4 step 2) and
    enforces audience + scope + expiry + signature on presentation.
    """

    rs_id: str
    scope_descriptions: dict[str, str]

    def well_known_aauth(self) -> dict:
        """The document the AS fetches at §4 step 2 (served in-process here)."""
        return {
            "resource": self.rs_id,
            "scope_descriptions": dict(self.scope_descriptions),
        }

    def validate_presented_token(
        self,
        token: str,
        *,
        issuer_jwks: dict,
        required_scope: str,
        now: int,
    ) -> tuple[dict, list[dict]]:
        """Check a presented token the way a resource server would.

        Returns ``(claims, checks)`` where ``checks`` is a list of
        ``{"check": ..., "passed": bool, "detail": ...}`` rows. Raises
        :class:`AAuthError` on the first hard failure so a caller cannot
        accidentally treat a failed check as a pass.

        Four checks run, in this order:
          1. **signature** — real Ed25519 verify of the compact JWS against
             the key named by ``kid`` in the issuer's JWKS.
          2. **audience**  — ``aud`` MUST equal this RS's identifier.
          3. **scope**     — ``scope`` MUST contain ``required_scope``.
          4. **expiry**    — ``exp`` MUST be in the future.
        """
        checks: list[dict] = []
        header_b64, payload_b64, sig_b64 = _split_jws(token)
        header = json.loads(_b64u_decode(header_b64))
        claims = json.loads(_b64u_decode(payload_b64))

        ok_sig = _verify_jws(token, issuer_jwks)
        checks.append(
            {
                "check": "signature",
                "passed": ok_sig,
                "detail": f"alg={header.get('alg')} kid={header.get('kid')} "
                f"verified against issuer JWKS (STUB issuer, real Ed25519)",
            }
        )
        if not ok_sig:
            raise AAuthError("token signature does not verify against the issuer JWKS")

        ok_aud = claims.get("aud") == self.rs_id
        checks.append(
            {
                "check": "audience",
                "passed": ok_aud,
                "detail": f"aud must equal {self.rs_id!r}",
            }
        )
        if not ok_aud:
            raise AAuthError(f"aud {claims.get('aud')!r} is not {self.rs_id!r}")

        granted = str(claims.get("scope", "")).split()
        ok_scope = required_scope in granted
        checks.append(
            {
                "check": "scope",
                "passed": ok_scope,
                "detail": f"{required_scope!r} must appear in the granted scope list",
            }
        )
        if not ok_scope:
            raise AAuthError(f"scope {required_scope!r} not granted (granted: {granted})")

        ok_exp = int(claims.get("exp", 0)) > now
        checks.append(
            {"check": "expiry", "passed": ok_exp, "detail": f"exp must be > {now}"}
        )
        if not ok_exp:
            raise AAuthError("token is expired")

        return claims, checks


# ---------------------------------------------------------------------------
# Authorization Server side — §3.1, §3.2, §4
# ---------------------------------------------------------------------------


@dataclass
class _PendingRequest:
    request_code: str
    client_id: str
    scope: str
    reason: str
    pii_elements: list[str]
    subject: str | None
    scope_descriptions: dict[str, str]
    approved: bool = False
    approver: str | None = None
    consent_shown: dict = field(default_factory=dict)


class StubAuthorizationServer:
    """An in-process AAuth AS. STUB — see this module's honest-limits note.

    Holds a real Ed25519 key and mints a real compact JWS, so every check the
    RS runs against it is a real check. It is a stub in exactly one respect:
    nothing about it was deployed, discovered, or operated by anybody.
    """

    def __init__(self, issuer: str, *, clock: int = 1_772_000_000) -> None:
        self.issuer = issuer
        self._key = Ed25519PrivateKey.generate()
        self._kid = hashlib.sha256(self._public_raw()).hexdigest()[:16]
        self._clock = clock
        self._pending: dict[str, _PendingRequest] = {}
        # §3.1: the AS maps a collected PII tuple to a user. A real AS does a
        # record lookup; here it is a dict, and the KEY is a tuple of element
        # NAMES plus a pre-agreed handle — never PII values.
        self._pii_map: dict[tuple, str] = {}
        # Stub client registry — §4 step 1 "Validates client credentials".
        self._clients: dict[str, str] = {}

    # -- registration helpers (a deployment does these out of band) ---------

    def register_client(self, client_id: str, client_secret: str) -> None:
        self._clients[client_id] = client_secret

    def register_subject(self, pii_elements: list[str], handle: str, subject: str) -> None:
        self._pii_map[(tuple(sorted(pii_elements)), handle)] = subject

    # -- key material -------------------------------------------------------

    def _public_raw(self) -> bytes:
        from cryptography.hazmat.primitives import serialization

        return self._key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def jwks(self) -> dict:
        """JWKS the RS fetches to check the token signature."""
        return {
            "keys": [
                {
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "alg": "EdDSA",
                    "use": "sig",
                    "kid": self._kid,
                    "x": _b64u(self._public_raw()),
                }
            ]
        }

    # -- §4: POST /agent_authorization -------------------------------------

    def agent_authorization(
        self,
        *,
        grant_type: str,
        client_id: str,
        client_secret: str,
        scope: str,
        reason: str,
        pii_elements: list[str],
        subject_handle: str,
        resource_server: ResourceServer,
    ) -> dict:
        """§4. Agent requests user approval by authenticating and POSTing here.

        ``reason`` MUST be echoed verbatim by the AS (§4) — it is returned in
        the response and shown to the human in :meth:`human_consent`.
        """
        if grant_type != AGENT_AUTHORIZATION_GRANT:
            raise AAuthError(
                f"grant_type MUST be {AGENT_AUTHORIZATION_GRANT} (§4); got {grant_type!r}"
            )
        # §4 step 1: validate client credentials.
        if self._clients.get(client_id) != client_secret:
            raise AAuthError("invalid_client (§4 step 1)")
        # §4 step 2: fetch each scope's description from the RS's
        # /.well-known/aauth.json#scope_descriptions.
        published = resource_server.well_known_aauth()["scope_descriptions"]
        descriptions = {}
        for s in scope.split():
            if s not in published:
                raise AAuthError(
                    f"scope {s!r} has no description at "
                    f"{resource_server.rs_id}/.well-known/aauth.json#scope_descriptions (§4 step 2)"
                )
            descriptions[s] = published[s]

        # §3.1: map the collected PII tuple to a user. Names + handle only.
        subject = self._pii_map.get((tuple(sorted(pii_elements)), subject_handle))
        if subject is None:
            # §3.1's whole point: a hallucinated tuple maps to no valid user
            # and the AS refuses to issue.
            raise AAuthError(
                "collected PII tuple does not map to a valid user — no token issued (§3.1)"
            )

        request_code = f"AAUTH-{uuid.uuid4().hex[:16].upper()}"
        self._pending[request_code] = _PendingRequest(
            request_code=request_code,
            client_id=client_id,
            scope=scope,
            reason=reason,  # echoed verbatim
            pii_elements=sorted(pii_elements),
            subject=subject,
            scope_descriptions=descriptions,
        )
        # §4 step 3 response shape.
        return {
            "request_code": request_code,
            "token_endpoint": f"{self.issuer}/token",
            "poll_interval": 5,
            "expires_in": 600,
            "poll_sse_endpoint": f"{self.issuer}/agent_authorization/sse",
            "reason": reason,  # "MUST be echoed verbatim by the AS" (§4)
            "scope_descriptions": descriptions,
        }

    # -- §3.2: the AS runs the human-in-the-loop, not the agent -------------

    def human_consent(self, request_code: str, *, approver: str, approve: bool) -> dict:
        """§3.2. The AS initiates the review, *displays* the reason and every
        scope description, authenticates the user, and binds approval to
        ``request_code``. Returns exactly what was displayed, so the record
        can commit to it.
        """
        req = self._pending.get(request_code)
        if req is None:
            raise AAuthError("unknown request_code")
        shown = {
            "reason": req.reason,
            "scope_descriptions": req.scope_descriptions,
            "authenticated_user": approver,
            "bound_to_request_code": request_code,
        }
        req.consent_shown = shown
        req.approved = bool(approve)
        req.approver = approver
        return shown

    # -- §4: POST /token (HTTP polling branch) ------------------------------

    def token(self, *, grant_type: str, client_id: str, device_code: str) -> dict:
        """§4 HTTP-polling branch. Pending -> ``authorization_pending``."""
        if grant_type != DEVICE_CODE_GRANT:
            raise AAuthError(
                f"polling MUST use {DEVICE_CODE_GRANT} (§4); got {grant_type!r}"
            )
        req = self._pending.get(device_code)
        if req is None or req.client_id != client_id:
            raise AAuthError("invalid_grant")
        if not req.approved:
            return dict(AUTHORIZATION_PENDING)  # §4 "Pending"
        access_token, claims = self._issue(req)
        # §4 "Success: Standard OAuth 2.x token response."
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 900,
            "issued_token_type": ISSUED_TOKEN_TYPE_JWT,
            "scope": req.scope,
            "_claims_for_demo_disclosure": claims,
        }

    def _issue(self, req: _PendingRequest) -> tuple[str, dict]:
        """Mint the compact JWS.

        Claim set note: §4 says "Details to be filled in" and does not fix a
        claim set. These are ordinary OAuth 2.1 / RFC 9068-shaped claims, not
        draft-mandated ones.
        """
        header = {"alg": "EdDSA", "typ": "at+jwt", "kid": self._kid}
        claims = {
            "iss": self.issuer,
            "sub": req.subject,
            "aud": _aud_for(req),
            "scope": req.scope,
            "client_id": req.client_id,
            "jti": f"aauth-grant-jti:{uuid.uuid4().hex}",
            "iat": self._clock,
            "exp": self._clock + 900,
            # Provenance of the authorization, not PII: which element NAMES
            # were collected (§3.1) and that a human approved (§3.2).
            "aauth_pii_elements": req.pii_elements,
            "aauth_hitl_approver": req.approver,
        }
        signing_input = f"{_b64u_json(header)}.{_b64u_json(claims)}".encode()
        sig = self._key.sign(signing_input)
        return f"{signing_input.decode()}.{_b64u(sig)}", claims


def _aud_for(req: _PendingRequest) -> str:
    """The RS a scope belongs to. Scopes are namespaced ``urn:<rs>:...`` here."""
    first = req.scope.split()[0]
    return first.rsplit(":", 1)[0]


# ---------------------------------------------------------------------------
# The capsule contract: digest-only authority commitment
# ---------------------------------------------------------------------------

#: Claims that get their own individual digest in the authority slot. The
#: job's requirement is sub/scope/aud; iss and jti round out "who issued this,
#: and which grant is it" without revealing anything the token holder needs.
COMMITTED_CLAIMS = ("iss", "sub", "aud", "scope")


def authority_commitment(claims: dict, *, spec_ref: str) -> dict:
    """Build the **digest-only** authority slot sealed into a capsule.

    Carries, in the clear: the grant's ``jti`` (an opaque identifier — the
    same choice ``examples/aauth-capsule-interop`` makes), ``exp``, the grant
    type, and the draft section this shape comes from. Carries, as digests
    only: ``iss``, ``sub``, ``aud``, ``scope``, plus a ``claims_digest`` over
    the whole committed subset so a verifier can check the set as a unit.

    **The raw token is never an input to a capsule and never appears here.**
    A verifier re-derives every digest from a separately disclosed claim set;
    see ``crossverify.py``.
    """
    committed = {k: claims[k] for k in COMMITTED_CLAIMS}
    slot = {
        "grant_type": AGENT_AUTHORIZATION_GRANT,
        "issued_token_type": ISSUED_TOKEN_TYPE_JWT,
        "spec_ref": spec_ref,
        "jti": claims["jti"],
        "exp": claims["exp"],
        "claims_digest": jcs_digest(committed),
        "raw_token_committed": False,
    }
    for k in COMMITTED_CLAIMS:
        slot[f"{k}_digest"] = jcs_digest(claims[k])
    return slot


def authority_reference(claims: dict) -> str:
    """The opaque string that goes in ``disposition.authority``."""
    return f"aauth:jti:{claims['jti']}"


def disclosure(claims: dict) -> dict:
    """The out-of-band claim set a verifier needs to re-derive the digests.

    This is the *disclosure*, not the token: it holds the committed claim
    values and no signature, so possessing it grants nothing.
    """
    return {k: claims[k] for k in (*COMMITTED_CLAIMS, "jti", "exp")}


# ---------------------------------------------------------------------------
# Minimal compact-JWS helpers (no JWT library — nothing here trusts a token)
# ---------------------------------------------------------------------------


def _b64u_decode(seg: str) -> bytes:
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def _split_jws(token: str) -> tuple[str, str, str]:
    parts = token.split(".")
    if len(parts) != 3:
        raise AAuthError(f"not a compact JWS (expected 3 segments, got {len(parts)})")
    return parts[0], parts[1], parts[2]


def _verify_jws(token: str, jwks: dict) -> bool:
    """Real Ed25519 verification of a compact JWS against a JWKS entry."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    header_b64, payload_b64, sig_b64 = _split_jws(token)
    header = json.loads(_b64u_decode(header_b64))
    keys = {k.get("kid"): k for k in jwks.get("keys", [])}
    jwk = keys.get(header.get("kid"))
    if jwk is None or jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519":
        return False
    pub = Ed25519PublicKey.from_public_bytes(_b64u_decode(jwk["x"]))
    try:
        pub.verify(_b64u_decode(sig_b64), f"{header_b64}.{payload_b64}".encode())
    except InvalidSignature:
        return False
    return True


def read_claims_unverified(token: str) -> dict:
    """Base64-decode the payload with no signature check — reads only what a
    stranger holding the token could already read. (Same discipline as the
    partner testbed's unverified-claims decode.)
    """
    return json.loads(_b64u_decode(_split_jws(token)[1]))
