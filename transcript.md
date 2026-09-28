# demo2 — executed transcript

**Regenerated 2026-09-03**, after the negotiation front-half was added
(acts 1-3), with readable pacing and the optional browser render.

Everything below is verbatim stdout from a real run on this machine. Nothing
is illustrative and nothing is hand-edited. Capsule IDs are minted live, so a
rerun produces different ones — that is expected and is exactly why no ID
here should ever be pre-printed on a slide.

**Executed against** (fresh venv, both installed from PyPI):

```
Python 3.10.12
agent-action-capsule   0.2.0
capsule-emit           0.7.0
checkpointed-local-log 0.1.0
cryptography           50.0.1
```

**Three runs, three exit codes:**

| Command | Exit |
|---|---|
| `python narrate.py --bundle evidence --fast --html` | 0 |
| `python crossverify.py --bundle evidence --mandate` | 0 |
| `python test_offline.py` | 0 |

`--fast` suppresses the narrated pauses so the transcript is text-identical to
what a watcher sees, without the timing. The default run (`python narrate.py`
on a terminal) prints the same lines with a ~1.2 s beat between them;
`--step` waits for Enter instead. Pauses are `time.sleep`/`input` only and
open no socket — `test_offline.py` runs the whole thing with the socket layer
bricked and still passes.

---

## 1. `python narrate.py --bundle evidence --fast --html`  → exit 0

```
==========================================================================
  demo2 — a negotiation you can watch, a record a stranger can check
==========================================================================
  bundle:  evidence
  pacing:  fast (no pauses)
  egress:  CAPSULE_WITNESS=off, CAPSULE_ANCHOR=off, AAC_ANCHOR_URL=off,
           every emitter anchor=False. No socket is opened by this script.

==========================================================================
  ACT 1 — The brief, the wicket, and two competing suppliers
==========================================================================
  think Before I opened a single conversation, a human approved what I am
        allowed to agree to. That brief is my wicket. The room sees it here
        because you are the audience; no supplier ever will.
        wicket  hard    29 units - ceiling 50.00/unit - net30 - lead <= 14d
        wicket  aim     open at 60% of quote, climb toward 43.00/unit, max 3 rounds
        wicket  digest  744670b20906b5ff6be2258e720479ddc951dfb03df285525fe1b2e61460606c
  think That digest is what gets sealed into the purchase order — not the
        ceiling, not the target. A stranger can later prove I stayed inside a
        mandate without ever learning what my ceiling was.
        seller  Frobozz Supply   Incumbent widget supplier. Regional warehouse, own freight
        desk.
        seller  Globex Corp      National distributor. Container-scale pricing, port-side lead
        times.
  think One brief, two suppliers, same wording to both — if the quotes differ,
        it is the sellers that differ, not the ask.
  ->    To Frobozz Supply and Globex Corp: RFQ-7777 — 29 x widget, net30, delivered inside 14
        days. Quote me.
  <-    Frobozz Supply: 52.00/unit  net15  12d lead   (1508.00 total)
        "List is $52.00 a unit, net15, twelve days out. No volume break at 29."
  <-    Globex Corp: 48.00/unit  net30  21d lead   (1392.00 total)
        "$48.00 a unit, net30 from the start, but I'm three weeks out."
  think Globex Corp is the cheaper opener at 48.00 but is 21 days out, which
        is outside the brief. Neither opener is close to where I am told to
        land. I counter both — every offer gets a counter.

==========================================================================
  ACT 2 — Counter-rounds — anchor low, then climb toward the target
==========================================================================
  think Anchoring at 60% of each seller's own quote. Not an insult — a probe:
        how far a supplier moves off its opener tells me where its floor
        actually is.
  ->    To Frobozz Supply: countering at 31.20/unit (60% of their 52.00) to anchor low.
  <-    Frobozz Supply: 47.50/unit  net30  12d lead   (1377.50 total)   (moved 4.50/unit)
        "$47.50 and I'll move you to net30 — the terms cost me less than the price does."
  ->    To Globex Corp: countering at 28.80/unit (60% of their 48.00) to anchor low.
  <-    Globex Corp: 46.00/unit  net30  16d lead   (1334.00 total)   (moved 2.00/unit)
        "$46.00. I can pull it to sixteen days; below that I'd be paying air freight."
  think Frobozz Supply moved 4.50 a unit off its opener; Globex Corp moved
        2.00. The one that moved further has further left to move. One more
        round, then I stop.
  think Climbing to 40.00/unit with both — deliberately short of where I am
        told to land, so I still have a move in hand. Same number to each, and
        each of them knows there is another quote on my desk.
  ->    To Frobozz Supply: 40.00/unit, net30, inside 14 days. I am comparing you against another
        quote.
  <-    Frobozz Supply: 42.00/unit  net30  10d lead   (1218.00 total)   [best and final]
        "$42.00, net30, ten days, and I absorb the expedited freight. That is best and final."
  ->    To Globex Corp: 40.00/unit, net30, inside 14 days. I am comparing you against another
        quote.
  <-    Globex Corp: 41.50/unit  net30  21d lead   (1203.50 total)   [best and final]
        "$41.50 — I'll beat anyone on price if you can take the three-week lead. That's the
        trade."

==========================================================================
  ACT 3 — The wicket check, and the pick
==========================================================================
  think Both are done moving. Now the part that is not haggling: does each
        final offer fit the brief my principal approved? That brief is private
        — the grading is not.
        wicket  Frobozz Supply   ELIGIBLE
        wicket  Globex Corp      OUT — fails lead_time
  think Globex Corp is the cheapest number on the table — 14.50 cheaper across
        the order. It is also outside a hard invariant, and a hard invariant
        is not mine to trade. The lowest price is not the winning price.
  think Frobozz Supply at 42.00/unit clears every invariant and beats the
        number I was told to land on. Over-negotiating a winning offer is how
        you lose it. I stop here.
  ->    To Frobozz Supply: selected. 29 units at 42.00, net30, 10 days — 1218.00 total. Raising
        the PO.
  ->    To Globex Corp: not this time — a constraint in my brief, not your price. I am not
        telling them which one.
      (13 negotiation frames recorded to wire.json — not printed here; the printed frames resume with AAuth.)
  ok  wicket privacy check: the ceiling and target strings appear in 0 of 13 wire frames
  ok  negotiation digest  ab457a5a44fe59ac7b738f0223b9dd21c1a34cf5a64b8575df397e102988255e
  ok  accepted offer      2dd3b2d16f0982b5d081f2cec26742d5186cfec515b7f3b5f5e7e7a87df3b70d
      the order the rest of this demo is about: PO-7777  Frobozz Supply  29 x widget @ 42.00  = $1218.00  net30

==========================================================================
  ACT 4 — AAuth §4 — POST /agent_authorization  (the 'may', requested)
==========================================================================
  The negotiation is over; nothing has been committed. Now the agent asks a human for permission to place it with Frobozz Supply.
    wire {"from": "acme-co/po-agent","kind": "POST /agent_authorization","payload": {"client_id": "acme-po-agent","grant_type": "urn:ietf:params:oauth:grant-type:agent_authorization","pii_elements_collected": ["full_name","date_of_birth","ssn_last4"],"reason": "Place purchase order PO-7777 ($1218.00, net30) with Frobozz Supply on your behalf.","scope": "urn:frobozz-supply:orders.submit urn:frobozz-supply:orders.read","subject_handle": "acme-user-handle-4417"},"seq": 14,"to": "as.acme-co.example"}
    wire {"from": "as.acme-co.example","kind": "200 agent_authorization","payload": {"expires_in": 600,"poll_interval": 5,"poll_sse_endpoint": "https://as.acme-co.example/agent_authorization/sse","reason": "Place purchase order PO-7777 ($1218.00, net30) with Frobozz Supply on your behalf.","request_code": "AAUTH-523E993C42D04A56","scope_descriptions": {"urn:frobozz-supply:orders.read": "Read the status of purchase orders you have placed.","urn:frobozz-supply:orders.submit": "Submit a purchase order to Frobozz Supply on your behalf."},"token_endpoint": "https://as.acme-co.example/token"},"seq": 15,"to": "acme-co/po-agent"}
  ok  request_code=AAUTH-523E993C42D04A56  poll_interval=5s
  ok  reason echoed verbatim by the AS, as §4 requires
      the reason carries the negotiated price — the human approves the deal the agent actually struck, not a blank cheque.
      PII: only element NAMES crossed this boundary — no PII values exist anywhere in this demo.

==========================================================================
  ACT 5 — AAuth §3.2 — the AS (not the agent) runs the consent review
==========================================================================
  The agent does not render UI and handles no redirect; it waits.
    wire {"from": "as.acme-co.example","kind": "200 token (poll #1)","payload": {"error": "authorization_pending"},"seq": 16,"to": "acme-co/po-agent"}
  ok  poll #1 -> {"error":"authorization_pending"}  (§4)
    displayed to the human (§3.2 step 2):
      urn:frobozz-supply:orders.submit
        -> Submit a purchase order to Frobozz Supply on your behalf.
      urn:frobozz-supply:orders.read
        -> Read the status of purchase orders you have placed.
  ok  authenticated dana@acme-co.example, approval bound to AAUTH-523E993C42D04A56

==========================================================================
  ACT 6 — AAuth §4 — POST /token  (the 'may', issued)
==========================================================================
    wire {"from": "as.acme-co.example","kind": "200 token (poll #2)","payload": {"access_token": "<redacted compact JWS: 3 segments, 74.526.86 chars, 688 bytes total>","expires_in": 900,"issued_token_type": "urn:ietf:params:oauth:token-type:jwt","scope": "urn:frobozz-supply:orders.submit urn:frobozz-supply:orders.read","token_type": "Bearer"},"seq": 17,"to": "acme-co/po-agent"}
  ok  issued_token_type=urn:ietf:params:oauth:token-type:jwt
    claims the agent now holds (shown here, never sealed in the clear):
      iss    https://as.acme-co.example
      sub    urn:acme-co:user:4417
      aud    urn:frobozz-supply
      scope  urn:frobozz-supply:orders.submit urn:frobozz-supply:orders.read
      jti    aauth-grant-jti:c7737f7e6b134ac6ac08c84bb2642d5e
      exp    1772000900

==========================================================================
  ACT 7 — Bilateral move 1 of 4 — request attestation over the shared digest
==========================================================================
  ok  subject_digest = SHA-256(JCS(order)) = e26a998baaf99379b32d9c60281f17f5318499a4b085e7c9ee6dee033ce2548c
  ok  acme-co's capsules will carry the grant as digests only: claims_digest=1794af89d1c931e9104350eb…, jti=c84bb2642d5e, raw_token_committed=False
  ok  acme-co producer key_id        3ef66c83e80f920d376c84e2523ef32fc7c546ba89c86e8010d700a2c72123e8
  ok  frobozz-supply producer key_id 6dd2f5a9b864345e32711184cbf592f5172058cc75b6c0b0c79efb2fae050b5f
  ok  state=requested  handshake_id=28b3fda6e150462396b9f873e74a4919

==========================================================================
  ACT 8 — BUY side — acme-co's own ledger  (the goose purchase-order story, kept)
==========================================================================
  [1] get_price          -> 42.00 USD/unit   50a9fe6d6d2d13fb… (fyi, unchained)
      (the catalogue number. The negotiated number is 42.00 — the haggle is why they differ.)
    wire {"from": "acme-co","kind": "order.submit","payload": {"buyer_capsule_id": "340827c389b185aeeac1d140c3b65b871e89552e10ab1c8d5f3a1c5efc0c7b4c","order": {"amount_usd": "1218.00","buyer": "Acme Co","currency": "USD","line_items": [{"qty": 29,"sku": "widget","unit_price_usd": "42.00"}],"po_number": "PO-7777","terms": "net30","vendor": "Frobozz Supply","vendor_operator": "frobozz-supply"},"subject_digest": "e26a998baaf99379b32d9c60281f17f5318499a4b085e7c9ee6dee033ce2548c"},"seq": 18,"to": "frobozz-supply"}
  [2] submit_order       -> dispatched  340827c389b185ae…  PO-7777 $1218.00
      carries mandate digests: wicket=744670b20906b5ff… (pass), offer=2dd3b2d16f0982b5…
  [3] approve_large_order-> BLOCKED     fe8eed1a256e9132…  PO-7778 $125,000.00, human refusal
      (a DIFFERENT order, a DIFFERENT vendor. PO-7777 — the one just negotiated — went through with Frobozz; PO-7778 to Globex did not.)
      (nothing prompts at runtime — the capsule RECORDS a denial a human made. Say this.)
  [4] escalate_to_manager-> executed    4bf3a968a4e497f4…  relation=escalates — the chain continues PAST the refusal

==========================================================================
  ACT 9 — SELL side — frobozz-supply's OWN ledger, OWN operator, OWN key
==========================================================================
    wire {"from": "acme-co","kind": "order.present_credential","payload": {"access_token": "<redacted compact JWS: 3 segments, 74.526.86 chars, 688 bytes total>","note": "the bearer token DOES cross the wire; it never enters a capsule","po_number": "PO-7777"},"seq": 19,"to": "frobozz-supply"}
    wire {"from": "frobozz-supply","kind": "order.accepted","payload": {"auth_checks": [{"check": "signature","passed": true},{"check": "audience","passed": true},{"check": "scope","passed": true},{"check": "expiry","passed": true}],"po_number": "PO-7777","seller_capsule_id": "aa0560d2bd6c39080bb2c2ec779057361529996211c7f21e8c13d8b67a97a835"},"seq": 20,"to": "acme-co"}
  [5] receive_order      -> executed    aa0560d2bd6c3908…
        auth check signature  PASS  alg=EdDSA kid=161645c8ef2b75f5 verified against issuer JWKS (STUB issuer, real Ed25519)
        auth check audience   PASS  aud must equal 'urn:frobozz-supply'
        auth check scope      PASS  'urn:frobozz-supply:orders.submit' must appear in the granted scope list
        auth check expiry     PASS  exp must be > 1772000000
        and commits the offer it won: 2dd3b2d16f0982b5… — the same digest the buyer sealed, from opposite sides of the table
  [6] fulfill_order      -> executed    cf8ab8cd69f68aed…  tracking GF-7777-1

==========================================================================
  ACT 10 — Bilateral moves 2-4 — action attestation + both acknowledgments
==========================================================================
  ok  move 2  responder signed the action  -> state=acted
  ok  move 3  requester acknowledged        -> state=acted
  ok  move 4  responder acknowledged        -> state=bilateral
  ok  every signature above verified with real Ed25519 against the same key each party's capsules name — not the module's no_op_verifier, not its HMAC dict_verifier
    wire {"from": "frobozz-supply","kind": "fulfillment.confirm","payload": {"cites_buyer_capsule_id": "340827c389b185aeeac1d140c3b65b871e89552e10ab1c8d5f3a1c5efc0c7b4c","confirmation": {"amount_usd": "1218.00","fulfillment_ref": "GF-7777-1","po_number": "PO-7777","status": "fulfilled"},"response_digest": "81be565e2026d25fdb5ba9d78eb974b9ae6070476b069445928a3a086ee993bc","seller_capsule_id": "b7fa1db19f34bb025eb080405eb5540dd9d3c0e7755bfeafb12358285dab3d40"},"seq": 21,"to": "acme-co"}
  [7] confirm_fulfillment-> confirmed   b7fa1db19f34bb02…
        cites acme-co's order capsule 340827c389b185ae… by content address

==========================================================================
  ACT 11 — Close-out — the buyer cites the SELLER's capsule, across the ledger line
==========================================================================
  [8] close_out_order    -> confirmed   ad9e5977ae33104a…
        cites frobozz-supply's confirm b7fa1db19f34bb02… by content address

  acme-co ledger:        5 capsules
    50a9fe6d6d2d…  get_price              [executed] effect=planned   
    340827c389b1…  submit_order           [executed] effect=dispatched
    fe8eed1a256e…  approve_large_order    [blocked ] effect=planned     -> 340827c389b1… (sequence)
    4bf3a968a4e4…  escalate_to_manager    [executed] effect=dispatched  -> fe8eed1a256e… (escalates)
    ad9e5977ae33…  close_out_order        [executed] effect=confirmed   -> b7fa1db19f34… (confirms)
  frobozz-supply ledger: 3 capsules
    aa0560d2bd6c…  receive_order          [executed] effect=dispatched
    cf8ab8cd69f6…  fulfill_order          [executed] effect=dispatched  -> aa0560d2bd6c… (confirms)
    b7fa1db19f34…  confirm_fulfillment    [executed] effect=confirmed   -> 340827c389b1… (confirms)

==========================================================================
  ACT 12 — Offline cross-verify — a stranger, both ledgers, no network, no trust
==========================================================================
  [C1] ok   acme-co: payload verify (5 capsules)                                       capsule_id recomputes + §5 structure holds; signature NOT checked here
  [C1] ok   frobozz-supply: payload verify (3 capsules)                                capsule_id recomputes + §5 structure holds; signature NOT checked here
  [C2] ok   acme-co: producer COSE_Sign1 signature                                     each capsule_id signed under the key named in key_id
  [C2] ok   frobozz-supply: producer COSE_Sign1 signature                              each capsule_id signed under the key named in key_id
  [C3] ok   acme-co: subject-bound (operator + key_id)                                 operator=['acme-co'] key_id=3ef66c83e80f920d…
  [C3] ok   frobozz-supply: subject-bound (operator + key_id)                          operator=['frobozz-supply'] key_id=6dd2f5a9b864345e…
  [C3] ok   two parties, two distinct producer keys                                    3ef66c83e80f920d… vs 6dd2f5a9b864345e…
  [C4] ok   acme-co: links resolvable within its own ledger alone                      1 cross-ledger citation(s) unresolvable alone (expected): [('ad9e5977ae33', 'b7fa1db19f34')]
  [C4] ok   frobozz-supply: links resolvable within its own ledger alone               1 cross-ledger citation(s) unresolvable alone (expected): [('b7fa1db19f34', '340827c389b1')]
  [C4] ok   union of both ledgers: every chain parent resolves                         8 capsules, 0 dangling links
  [C5] ok   the three bilateral capsules are present                                   submit_order / confirm_fulfillment / close_out_order
  [C5] ok   both parties committed the SAME subject_digest                             e26a998baaf99379b32d9c60…
  [C5] ok   seller's confirm cites buyer's order by content address                    b7fa1db19f34… -> 340827c389b1…
  [C5] ok   buyer's close-out cites seller's confirm by content address                ad9e5977ae33… -> b7fa1db19f34…
  [C6] ok   acme-co (held grant): claim digests recompute from disclosure              iss/sub/aud/scope + claims_digest match, jti=c84bb2642d5e
  [C6] ok   acme-co (held grant): record asserts no raw token committed                raw_token_committed=false
  [C6] ok   frobozz-supply (presented grant): claim digests recompute from disclosure  iss/sub/aud/scope + claims_digest match, jti=c84bb2642d5e
  [C6] ok   frobozz-supply (presented grant): record asserts no raw token committed    raw_token_committed=false
  [C7] ok   raw access token absent from both ledgers                                  searched 4 needles (whole token + each segment) across 23175 bytes

  -> 19 checks, 0 failures. Bundle VERIFIES.

  Beyond the 19 — the negotiation's own commitments, rechecked from the bundle's files:
     ok   wicket digest recomputes from wicket.json                        744670b20906b5ff6be2258e… vs sealed 744670b20906b5ff6be2258e…
     ok   negotiation digest recomputes from negotiation.json              3 rounds, ab457a5a44fe59ac7b738f02…
     ok   accepted-offer digest recomputes from the winner block           frobozz-supply @ 42.00/unit
     ok   both ledgers sealed the same accepted-offer digest               buyer 2dd3b2d16f0982b5… / seller 2dd3b2d16f0982b5…
     ok   winner regraded against the disclosed hard invariants            4 invariants rechecked, 0 failed; record claims 'pass'
     ok   order hashing to the sealed subject_digest IS the winning offer  Frobozz Supply 29 @ 42.00 net30 = 1218.00; subject_digest recomputes=True
     (these are NOT part of the 19 above — they are a separate, opt-in section: crossverify.py --bundle <dir> --mandate)

  --- tamper: capsule_id ------------------------------------
  TAMPER [capsule_id]: added a field to acme-co's submit_order capsule after it was sealed (the classic post-hoc edit)
  [C1] FAIL acme-co: payload verify (5 capsules)    1 failed: [('340827c389b1', ['recomputed 7f7789d8868e42d458ce92ad9594c9bd910c594eb3d4bb15376ba200dfc6dcb7 != carried 340827c389b185aeeac1d140c3b65b871e89552e10ab1c8d5f3a1c5efc0c7b4c'])]
  [C2] FAIL acme-co: producer COSE_Sign1 signature  1 failed: ['340827c389b1']

  -> 2 check(s) FAILED; the tamper was detected.
     in plain terms: a field was added after sealing -> the record no longer hashes to its own id, and the signature was over the old id (C1 + C2).
  --- tamper: output_digest ---------------------------------
  TAMPER [output_digest]: flipped one hex character of frobozz-supply's confirm output digest
  [C1] FAIL frobozz-supply: payload verify (3 capsules)    1 failed: [('b7fa1db19f34', ['recomputed 22e0ec470ebc38cf23cd8c64fabefd6ea604fcaf95b901991cb57d6a6bb9cdac != carried b7fa1db19f34bb025eb080405eb5540dd9d3c0e7755bfeafb12358285dab3d40', 'chain parent-existence and concurrent-supersedes are store-level checks (§6); not run without a store', "effect.type='confirm_fulfillment' is not a seeded effect.type value; informational, not rejected (§12)"])]
  [C2] FAIL frobozz-supply: producer COSE_Sign1 signature  1 failed: ['b7fa1db19f34']

  -> 2 check(s) FAILED; the tamper was detected.
     in plain terms: one hex char of an output digest flipped -> the id recomputes differently and the signature no longer matches (C1 + C2).
  --- tamper: cross_citation --------------------------------
  TAMPER [cross_citation]: repointed the seller's confirm at a different (non-existent) buyer capsule
  [C1] FAIL frobozz-supply: payload verify (3 capsules)              1 failed: [('b7fa1db19f34', ['recomputed 2d3a9ac46cb738991873ec577d93b0de161b5c4a90038a4df67e54f189db651e != carried b7fa1db19f34bb025eb080405eb5540dd9d3c0e7755bfeafb12358285dab3d40', 'chain parent-existence and concurrent-supersedes are store-level checks (§6); not run without a store', "effect.type='confirm_fulfillment' is not a seeded effect.type value; informational, not rejected (§12)"])]
  [C2] FAIL frobozz-supply: producer COSE_Sign1 signature            1 failed: ['b7fa1db19f34']
  [C4] FAIL union of both ledgers: every chain parent resolves       unresolved: [('b7fa1db19f34', 'ffffffffffff')]
  [C5] FAIL seller's confirm cites buyer's order by content address  cites ffffffffffff…, expected 340827c389b1…

  -> 4 check(s) FAILED; the tamper was detected.
     in plain terms: the cross-ledger pointer was repointed at a capsule that does not exist -> the id breaks, the union has a dangling link, and the citation no longer matches (C1 + C2 + C4 + C5).
  --- tamper: authority_scope -------------------------------
  TAMPER [authority_scope]: widened the disclosed AAuth scope after the fact (claiming a permission the grant never carried)
  [C6] FAIL acme-co (held grant): claim digests recompute from disclosure              mismatched=['scope'] claims_digest_ok=False jti_ok=True
  [C6] FAIL frobozz-supply (presented grant): claim digests recompute from disclosure  mismatched=['scope'] claims_digest_ok=False jti_ok=True

  -> 2 check(s) FAILED; the tamper was detected.
     in plain terms: the DISCLOSED AAuth scope was widened after the fact -> the sealed scope/claims digests no longer recompute from the disclosure (C6).

==========================================================================
  What this run established
==========================================================================
  a negotiation with two competing suppliers, 3 rounds, a winner picked against a private brief
  the winner's identity is what named the resource server, the scopes a
  human approved, and the operator on every sell-side capsule
  two ledgers, 5 + 3 capsules, two distinct producer keys
  one transaction: both sides committed the same subject_digest
  each side's confirm/close-out cites the other's capsule by content address
  AAuth claims sealed as digests only; the raw token is in neither ledger
  every capsule verifies offline; four separate tampers each broke a check

  What it did NOT establish (say these unprompted):
   - the negotiation itself is SCRIPTED. Fixed ladders, no model, no
     counterparties. It shows the shape of a haggle, not that one happened.
   - the offers and counters are NOT sealed as capsules. What is sealed is
     the digest of the negotiation record and of the winning offer, so an
     altered transcript stops matching — but a negotiation nobody wrote
     down leaves no trace either way.
   - no signature was checked on any AGENT CARD or DNS record; key
     ownership is bound only to this bundle's parties.json
   - the AAuth AS is a stub in this process. Its signature is real; its
     deployment is not.
   - no human was prompted at runtime. The capsule records a refusal a
     human made.
   - integrity, not completeness: nothing here proves a party did not
     omit a record it never wrote down.

  bundle kept at: evidence
  re-check it any time:  python crossverify.py --bundle evidence

  browser render: evidence/index.html
  open it with:   file:///home/thisjody_gmail_com/asg/buildshift/workspace/demo2-negotiation/tree/examples/demo2/evidence/index.html
  self-contained: inline CSS, no <script>, no external URL, no CDN (checked)
==========================================================================
```

---

## 2. `python crossverify.py --bundle evidence --mandate`  → exit 0

The stranger's tool, standalone. It imports neither agent; it reads only the
published bundle. `--mandate` adds the negotiation's own commitments as a
*separate* section — deliberately not folded into the headline 19.

```
  [C1] ok   acme-co: payload verify (5 capsules)                                       capsule_id recomputes + §5 structure holds; signature NOT checked here
  [C1] ok   frobozz-supply: payload verify (3 capsules)                                capsule_id recomputes + §5 structure holds; signature NOT checked here
  [C2] ok   acme-co: producer COSE_Sign1 signature                                     each capsule_id signed under the key named in key_id
  [C2] ok   frobozz-supply: producer COSE_Sign1 signature                              each capsule_id signed under the key named in key_id
  [C3] ok   acme-co: subject-bound (operator + key_id)                                 operator=['acme-co'] key_id=3ef66c83e80f920d…
  [C3] ok   frobozz-supply: subject-bound (operator + key_id)                          operator=['frobozz-supply'] key_id=6dd2f5a9b864345e…
  [C3] ok   two parties, two distinct producer keys                                    3ef66c83e80f920d… vs 6dd2f5a9b864345e…
  [C4] ok   acme-co: links resolvable within its own ledger alone                      1 cross-ledger citation(s) unresolvable alone (expected): [('ad9e5977ae33', 'b7fa1db19f34')]
  [C4] ok   frobozz-supply: links resolvable within its own ledger alone               1 cross-ledger citation(s) unresolvable alone (expected): [('b7fa1db19f34', '340827c389b1')]
  [C4] ok   union of both ledgers: every chain parent resolves                         8 capsules, 0 dangling links
  [C5] ok   the three bilateral capsules are present                                   submit_order / confirm_fulfillment / close_out_order
  [C5] ok   both parties committed the SAME subject_digest                             e26a998baaf99379b32d9c60…
  [C5] ok   seller's confirm cites buyer's order by content address                    b7fa1db19f34… -> 340827c389b1…
  [C5] ok   buyer's close-out cites seller's confirm by content address                ad9e5977ae33… -> b7fa1db19f34…
  [C6] ok   acme-co (held grant): claim digests recompute from disclosure              iss/sub/aud/scope + claims_digest match, jti=c84bb2642d5e
  [C6] ok   acme-co (held grant): record asserts no raw token committed                raw_token_committed=false
  [C6] ok   frobozz-supply (presented grant): claim digests recompute from disclosure  iss/sub/aud/scope + claims_digest match, jti=c84bb2642d5e
  [C6] ok   frobozz-supply (presented grant): record asserts no raw token committed    raw_token_committed=false
  [C7] ok   raw access token absent from both ledgers                                  searched 4 needles (whole token + each segment) across 23175 bytes

  -> 19 checks, 0 failures. Bundle VERIFIES.

  Beyond the 19 — the negotiation's own commitments:
     ok   wicket digest recomputes from wicket.json                        744670b20906b5ff6be2258e… vs sealed 744670b20906b5ff6be2258e…
     ok   negotiation digest recomputes from negotiation.json              3 rounds, ab457a5a44fe59ac7b738f02…
     ok   accepted-offer digest recomputes from the winner block           frobozz-supply @ 42.00/unit
     ok   both ledgers sealed the same accepted-offer digest               buyer 2dd3b2d16f0982b5… / seller 2dd3b2d16f0982b5…
     ok   winner regraded against the disclosed hard invariants            4 invariants rechecked, 0 failed; record claims 'pass'
     ok   order hashing to the sealed subject_digest IS the winning offer  Frobozz Supply 29 @ 42.00 net30 = 1218.00; subject_digest recomputes=True
```

---

## 3. `python test_offline.py`  → exit 0

`socket.socket`, `socket.create_connection`, `socket.getaddrinfo` and
`ssl.SSLContext.wrap_socket` are each replaced with a function that raises,
and then the entire demo — negotiation, AAuth stub, both emitters, the
cross-verifier, the four tampers and the `--html` render — runs to completion.
Full narrator output is omitted here (it is section 1); the verdict:

```
==========================================================================

test_offline: narrate.main() returned 0 with the socket layer bricked.
test_offline: PASS — no network call was attempted anywhere in the run.
```
