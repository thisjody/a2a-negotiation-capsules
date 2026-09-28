#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render one demo2 run to a single self-contained HTML file.

Shape borrowed from the accountable deal-room's server-rendered room view
(``app/routes/room_view.py``): status badges, offer cards, a green "sealed
binding" box, then the verification. What is **not** borrowed is the server —
that view is a FastAPI route rendering live store state; this is a function
that takes a finished run and returns a string.

The rules this file exists to keep:

* **no network, ever.** No ``<script>``, no ``<link>``, no ``<img src>``, no
  CDN, no web font, no favicon fetch. Inline CSS only, system font stack only.
  ``assert_offline()`` greps the produced document for every one of those and
  is called by ``narrate.py`` on the output it just wrote — a claim that is
  checked is worth more than a claim that is documented.
* **same content as the terminal.** The rows in the verify table are the
  *same* ``Report`` rows the terminal printed, passed in, not recomputed. If
  the browser and the terminal ever disagree, that is a bug, and reusing the
  rows is how it stays impossible.
* **the terminal is still primary.** This is an ``--html`` also-render for
  people who want to read the run back, or scroll it during a hallway
  conversation. Nothing in the demo depends on it.

Opens with ``file://``. Works with the machine's network cable unplugged,
which is the only test that matters here.
"""
from __future__ import annotations

import html
import re
from typing import Iterable

# Everything that would make the browser reach for something. Checked against
# the rendered output, not just intended.
# Note it greps for *fetching constructs*, not for the string "http". An AAuth
# issuer claim is legitimately ``https://as.acme-co.example`` and is rendered as
# escaped text; text cannot fetch. Elements and attributes can, so those are
# what get banned.
_FORBIDDEN = (
    (r"<script", "a <script> tag"),
    (r"<link\b", "a <link> tag (stylesheet or icon)"),
    (r"<iframe", "an <iframe>"),
    (r"<img\b", "an <img> tag"),
    (r"<(embed|object|video|audio|source)\b", "an embedded-media tag"),
    (r"<form\b", "a <form> (it could submit somewhere)"),
    (r"\bsrc\s*=", "a src= attribute"),
    (r"\bhref\s*=", "an href= attribute"),
    (r"\bon[a-z]+\s*=\s*[\"']", "an inline event handler"),
    (r"@import", "a CSS @import"),
    (r"url\s*\(", "a CSS url()"),
)

CSS = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
     max-width:900px;margin:0 auto;padding:32px 20px 80px;background:#f8fafc;color:#1e293b;
     line-height:1.5}
h1{font-size:1.5rem;margin:0 0 4px}
h2{font-size:1.05rem;margin:34px 0 10px;padding-bottom:6px;border-bottom:1px solid #e2e8f0;
   letter-spacing:.02em;text-transform:uppercase;color:#475569;font-weight:700}
h3{font-size:.95rem;margin:18px 0 8px}
p{margin:8px 0}
.sub{color:#64748b;font-size:.9rem;margin:0 0 14px}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.75rem;
       font-weight:700;letter-spacing:.03em;margin-right:6px}
.b-ok{background:#dcfce7;color:#166534}
.b-bad{background:#fee2e2;color:#991b1b}
.b-info{background:#e0e7ff;color:#3730a3}
.b-warn{background:#fef3c7;color:#92400e}
.hash{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.72rem;
      word-break:break-all;color:#64748b}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;margin:10px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.offer{background:#fff;border:1px solid #e2e8f0;border-left-width:4px;border-radius:8px;
       padding:12px 14px}
.offer .who{font-weight:700}
.offer .price{font-size:1.3rem;font-weight:700;margin:4px 0}
.offer .terms{color:#475569;font-size:.85rem}
.offer .said{color:#334155;font-size:.85rem;font-style:italic;margin-top:8px}
.win{border-left-color:#10b981;background:#f0fdf4}
.out{border-left-color:#ef4444}
.neutral{border-left-color:#94a3b8}
.think{border-left:3px solid #c7d2fe;background:#eef2ff;padding:8px 12px;margin:8px 0;
       border-radius:0 6px 6px 0;font-size:.9rem}
.move{padding:6px 12px;margin:4px 0;font-size:.9rem;border-left:3px solid #e2e8f0}
.move.out{border-left-color:#3b82f6}
.move.in{border-left-color:#f59e0b}
.move .dir{font-family:ui-monospace,monospace;color:#94a3b8;margin-right:8px}
.said-line{color:#475569;font-size:.85rem;font-style:italic;padding:2px 12px 6px 24px}
.note-line{color:#475569;font-size:.85rem;font-family:ui-monospace,monospace;padding:2px 12px}
.binding{background:#ecfdf5;border:1px solid #10b981;border-radius:10px;padding:16px;margin:14px 0}
table{border-collapse:collapse;width:100%;margin:8px 0}
td,th{padding:6px 9px;border:1px solid #e2e8f0;text-align:left;font-size:.82rem;
      vertical-align:top}
th{background:#f1f5f9;font-weight:600}
tr.fail td{background:#fef2f2}
.wicket{background:#1e293b;color:#e2e8f0;border-radius:10px;padding:14px 16px;margin:10px 0;
        font-family:ui-monospace,monospace;font-size:.82rem}
.wicket .k{color:#94a3b8}
.tamper{margin:12px 0}
.tamper h3{margin-bottom:4px}
.limits li{margin:6px 0;font-size:.9rem}
.foot{margin-top:40px;padding-top:14px;border-top:1px solid #e2e8f0;color:#94a3b8;
      font-size:.78rem}
"""


def e(x) -> str:
    """Escape anything into safe text. Every dynamic value goes through here."""
    return html.escape(str(x), quote=True)


def _badge(text: str, kind: str = "info") -> str:
    return f'<span class="badge b-{kind}">{e(text)}</span>'


def _rows_table(rows: Iterable, headers=("check", "what", "verdict", "detail")) -> str:
    out = ["<table><tr>" + "".join(f"<th>{e(h)}</th>" for h in headers) + "</tr>"]
    for check, name, verdict, detail in rows:
        cls = ' class="fail"' if verdict != "PASS" else ""
        mark = "ok" if verdict == "PASS" else "FAIL"
        out.append(
            f"<tr{cls}><td>{e(check)}</td><td>{e(name)}</td>"
            f"<td><strong>{e(mark)}</strong></td><td>{e(detail)}</td></tr>")
    out.append("</table>")
    return "".join(out)


def _offer_card(offer: dict, *, klass: str = "neutral", tag: str = "") -> str:
    counter = offer.get("buyer_counter_usd")
    moved = offer.get("moved_usd")
    bits = []
    if counter:
        bits.append(f"after buyer's {e(counter)} counter")
    if moved and moved != "0.00":
        bits.append(f"moved {e(moved)}/unit")
    meta = " &middot; ".join(bits)
    return f"""<div class="offer {klass}">
<div class="who">{e(offer['seller_display'])} {tag}</div>
<div class="price">${e(offer['unit_price_usd'])}<span style="font-size:.8rem;font-weight:400">/unit</span></div>
<div class="terms">{e(offer['payment_terms'])} &middot; {e(offer['lead_time_days'])}d lead &middot; ${e(offer['total_usd'])} total</div>
{f'<div class="terms">{meta}</div>' if meta else ''}
<div class="said">&ldquo;{e(offer['said'])}&rdquo;</div>
</div>"""


def _capsule_table(records: list[dict]) -> str:
    out = ["<table><tr><th>capsule_id</th><th>action</th><th>verdict</th>"
           "<th>effect</th><th>chains to</th></tr>"]
    for r in records:
        chain = r.get("chain") or {}
        parent = chain.get("parent_capsule_id")
        link = f"{parent[:12]}… ({chain.get('relation')})" if parent else "—"
        out.append(
            f'<tr><td class="hash">{e(r["capsule_id"][:20])}…</td>'
            f'<td>{e(str(r.get("action_id", "?")).split("/")[0])}</td>'
            f'<td>{e(r["disposition"]["verdict_class"])}</td>'
            f'<td>{e(r.get("effect", {}).get("status", "?"))}</td>'
            f'<td class="hash">{e(link)}</td></tr>')
    out.append("</table>")
    return "".join(out)


def render(run: dict) -> str:
    """Turn a finished run into one HTML document. Pure function, no I/O."""
    neg = run["negotiation"]
    winner = neg["winner"] or {}
    order = run["order"]
    v = run["verify"]
    parts: list[str] = []

    parts.append(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>demo2 — negotiation, two ledgers, cross-verify</title>
<style>{CSS}</style>
</head><body>""")

    # ---- header -----------------------------------------------------------
    verdict_badge = _badge(f"{v['checks']} CHECKS, {v['failures']} FAILURES",
                           "ok" if v["failures"] == 0 else "bad")
    parts.append(f"""<h1>demo2 — a negotiation you can watch, a record a stranger can check</h1>
<p class="sub">Two competing suppliers, three narrated rounds, one winner — then two
independent ledgers, an offline cross-verify and four tamper injections.
This page is a render of one executed run; it contains no script and fetches nothing.</p>
<p>{verdict_badge}{_badge('4 TAMPERS DETECTED', 'ok')}{_badge('OFFLINE', 'info')}
{_badge('SCRIPTED NEGOTIATION', 'warn')}</p>
<div class="card">
<table>
<tr><th>bundle</th><td class="hash">{e(run['bundle'])}</td></tr>
<tr><th>pacing</th><td>{e(run['pacing'])}</td></tr>
<tr><th>egress</th><td>CAPSULE_WITNESS=off, CAPSULE_ANCHOR=off, AAC_ANCHOR_URL=off;
every emitter anchor=False. No socket opened.</td></tr>
</table></div>""")

    # ---- the wicket -------------------------------------------------------
    from negotiate import WICKET  # local import: keeps this module import-cheap
    hi, ng = WICKET["hard_invariants"], WICKET["negotiation"]
    parts.append(f"""<h2>The wicket — the buyer's private brief</h2>
<p>Approved by a human before the agent started. The audience sees it here; no
supplier ever does. What gets sealed into the purchase order is its
<em>digest</em> and a pass/fail — never the ceiling, never the target.</p>
<div class="wicket">
<div><span class="k">hard  </span> {e(hi['quantity'])} units &middot;
 ceiling {e(hi['unit_ceiling_usd'])}/unit &middot; {e(hi['required_payment_terms'])} &middot;
 lead &le; {e(hi['max_lead_time_days'])}d</div>
<div><span class="k">aim   </span> open at {e(ng['open_counter_pct_of_quote'])}% of quote,
 climb toward {e(ng['unit_target_usd'])}/unit, max {e(ng['max_rounds'])} rounds</div>
<div><span class="k">digest</span> {e(neg['wicket_digest'])}</div>
</div>
<p class="sub">Privacy check, run mechanically at the end of the negotiation: the
ceiling and target strings appear in
<strong>{e(len(neg['privacy_check']['leaked']))}</strong> of
{e(neg['privacy_check']['frames_searched'])} wire frames.</p>""")

    # ---- the negotiation --------------------------------------------------
    parts.append("<h2>The negotiation</h2>")
    for rnd in neg["rounds"]:
        label = f"Round {rnd['round']} — {rnd['kind']}"
        if rnd.get("counter_usd"):
            label += f" (buyer at ${rnd['counter_usd']}/unit)"
        parts.append(f"<h3>{e(label)}</h3><div class=\"grid\">")
        for o in rnd["offers"]:
            is_win = (rnd["round"] == neg["rounds"][-1]["round"]
                      and o["seller"] == winner.get("seller"))
            parts.append(_offer_card(
                o, klass="win" if is_win else "neutral",
                tag=_badge("SELECTED", "ok") if is_win else ""))
        parts.append("</div>")

    # ---- the narration, verbatim -----------------------------------------
    parts.append("""<h2>What the buyer said, and why — verbatim</h2>
<p class="sub">The same lines the terminal printed, in the same order. Reasoning
first, then the move.</p>""")
    neg_acts = {a["n"] for a in run["acts"][:3]}
    for line in run["narration"]:
        if line["act"] not in neg_acts:
            continue
        kind, text = line["kind"], line["text"]
        if kind == "think":
            parts.append(f'<div class="think">{e(text)}</div>')
        elif kind == "out":
            parts.append(f'<div class="move out"><span class="dir">&rarr;</span>{e(text)}</div>')
        elif kind == "in":
            parts.append(f'<div class="move in"><span class="dir">&larr;</span>{e(text)}</div>')
        elif kind == "said":
            parts.append(f'<div class="said-line">{e(text)}</div>')
        else:
            parts.append(f'<div class="note-line">{e(text)}</div>')

    # ---- the wicket grading ----------------------------------------------
    parts.append("""<h2>The wicket check — why the cheapest offer did not win</h2>
<table><tr><th>supplier</th><th>final</th><th>terms</th><th>lead</th>
<th>invariants</th><th>verdict</th></tr>""")
    for f in neg["final"]:
        failed = [c["invariant"] for c in f["wicket_checks"] if not c["passed"]]
        cls = "" if f["eligible"] else ' class="fail"'
        parts.append(
            f'<tr{cls}><td>{e(f["seller_display"])}</td>'
            f'<td><strong>${e(f["unit_price_usd"])}</strong></td>'
            f'<td>{e(f["payment_terms"])}</td><td>{e(f["lead_time_days"])}d</td>'
            f'<td>{e(", ".join(c["invariant"] + ("" if c["passed"] else " ✗") for c in f["wicket_checks"]))}</td>'
            f'<td>{"ELIGIBLE" if f["eligible"] else "OUT — " + e(", ".join(failed))}</td></tr>')
    parts.append("</table>")

    # ---- the winner feeds the flow ---------------------------------------
    parts.append(f"""<h2>The winner becomes the counterparty</h2>
<div class="binding">
<h3 style="margin-top:0">{e(winner.get('seller_display', '—'))} &mdash; {e(order['po_number'])}</h3>
<table>
<tr><th>order</th><td>{e(order['line_items'][0]['qty'])} &times;
 {e(order['line_items'][0]['sku'])} @ ${e(order['line_items'][0]['unit_price_usd'])}/unit
 = <strong>${e(order['amount_usd'])}</strong> {e(order['terms'])}</td></tr>
<tr><th>subject_digest</th><td class="hash">{e(run['subject_digest'])}</td></tr>
<tr><th>wicket digest / result</th><td class="hash">{e(run['mandate']['wicket_digest'])}
 &mdash; {e(run['mandate']['wicket_result'])}</td></tr>
<tr><th>negotiation digest</th><td class="hash">{e(run['mandate']['negotiation_digest'])}</td></tr>
<tr><th>accepted offer digest</th><td class="hash">{e(run['accepted_offer_digest'])}</td></tr>
<tr><th>bilateral state</th><td>{e(run['bilateral']['state'])} &middot; handshake
 <span class="hash">{e(run['bilateral']['handshake_id'])}</span></td></tr>
</table>
<p class="sub" style="margin-bottom:0">The winner's identity is what named the AAuth
resource server, the scopes a human approved, and the operator stamped on every
sell-side capsule.</p>
</div>""")

    # ---- authority --------------------------------------------------------
    a = run["aauth"]
    parts.append(f"""<h2>Authority — AAuth says who may act</h2>
<div class="card">
<p><strong>request_code</strong> <span class="hash">{e(a['request_code'])}</span> &middot;
<strong>issued_token_type</strong> <span class="hash">{e(a['issued_token_type'])}</span> &middot;
approved by {e(a['approver'])}</p>
<p>What the Authorization Server displayed to the human (draft §3.2 step 2):</p>
<table><tr><th>scope</th><th>description shown</th></tr>""")
    for k, val in a["scope_descriptions"].items():
        parts.append(f"<tr><td class=\"hash\">{e(k)}</td><td>{e(val)}</td></tr>")
    parts.append("</table><p>Claims the agent holds — sealed into the capsules as "
                 "<em>digests only</em>:</p><table>")
    for k, val in a["claims"].items():
        parts.append(f"<tr><th>{e(k)}</th><td class=\"hash\">{e(val)}</td></tr>")
    parts.append("</table><p>The seller's checks on the token it was shown:</p><table>"
                 "<tr><th>check</th><th>result</th><th>detail</th></tr>")
    for c in run["auth_checks"]:
        cls = "" if c["passed"] else ' class="fail"'
        parts.append(f'<tr{cls}><td>{e(c["check"])}</td>'
                     f'<td><strong>{"PASS" if c["passed"] else "FAIL"}</strong></td>'
                     f'<td>{e(c["detail"])}</td></tr>')
    parts.append("</table></div>")

    # ---- the two ledgers --------------------------------------------------
    parts.append(f"""<h2>Two ledgers, two operators, two keys</h2>
<div class="card"><h3>{e(run['parties']['buyer'])} &mdash;
 {e(len(run['buyer_records']))} capsules</h3>
<p class="hash">key_id {e(run['keys'][run['parties']['buyer']])}</p>
{_capsule_table(run['buyer_records'])}</div>
<div class="card"><h3>{e(run['parties']['seller'])} &mdash;
 {e(len(run['seller_records']))} capsules</h3>
<p class="hash">key_id {e(run['keys'][run['parties']['seller']])}</p>
{_capsule_table(run['seller_records'])}</div>""")

    # ---- cross-verify -----------------------------------------------------
    parts.append(f"""<h2>Offline cross-verify — a stranger, both ledgers, no trust</h2>
<p>{verdict_badge}</p>
{_rows_table(run['verify']['rows'])}""")

    parts.append("""<h3>Beyond the 19 — the negotiation's own commitments</h3>
<p class="sub">A separate, opt-in section
(<code>crossverify.py --bundle &lt;dir&gt; --mandate</code>). Deliberately not folded
into the headline count.</p>
<table><tr><th>what</th><th>verdict</th><th>detail</th></tr>""")
    for row in run["mandate_rows"]:
        cls = "" if row["passed"] else ' class="fail"'
        parts.append(f'<tr{cls}><td>{e(row["name"])}</td>'
                     f'<td><strong>{"ok" if row["passed"] else "FAIL"}</strong></td>'
                     f'<td>{e(row["detail"])}</td></tr>')
    parts.append("</table>")

    # ---- tampers ----------------------------------------------------------
    parts.append("<h2>Four tampers, four different failures</h2>")
    for t in run["tampers"]:
        parts.append(f"""<div class="tamper card">
<h3>--tamper {e(t['kind'])} {_badge(f"{len(t['failures'])} CHECKS FAILED", 'bad')}</h3>
<p class="sub">{e(t['says'])}.</p>
{_rows_table(t['failures'])}
</div>""")

    # ---- honest limits ----------------------------------------------------
    parts.append("""<h2>What this run did NOT establish</h2>
<ul class="limits">
<li><strong>The negotiation is scripted.</strong> Fixed ladders, no model, no live
counterparties. It shows the <em>shape</em> of a haggle, not that one happened.</li>
<li><strong>The offers and counters are not sealed as capsules.</strong> What is sealed
is the digest of the negotiation record and of the winning offer, so an altered
transcript stops matching — but a negotiation nobody wrote down leaves no trace
either way.</li>
<li><strong>No identity binding.</strong> No agent card, no JWKS URL, no DNS record.
<code>key_id &rarr; operator</code> is bound only by this bundle's
<code>parties.json</code>. The producer signature proves the <em>holder of a key</em>
sealed a record, never who that key belongs to.</li>
<li><strong>The AAuth Authorization Server is a stub in this process.</strong> Its
Ed25519 key is real and its JWS genuinely verifies; nothing about it was deployed,
discovered or operated.</li>
<li><strong>No human was prompted at runtime</strong>, on either the consent review or
the $125,000 refusal. The capsule <em>records</em> a decision a human made.</li>
<li><strong>Integrity, not completeness.</strong> Nothing here proves a party did not
simply decline to write a record down.</li>
<li><strong>Nothing here is a standard.</strong>
<code>draft-rosenberg-oauth-aauth-01</code>,
<code>draft-mih-scitt-agent-action-capsule-04</code> and
<code>draft-mih-agent-bilateral-attestation-00</code> are individual Internet-Drafts,
work in progress, not WG-adopted.</li>
</ul>""")

    parts.append("""<p class="foot">demo2 &mdash; rendered offline by
<code>render_html.py</code>: inline CSS, no script, no external reference of any kind.
Negotiation shape adapted from the accountable deal-room's room view and DJ-buyer
skill; rebuilt scripted and offline. Prepared with AI-agent assistance under human
direction.</p>
</body></html>""")

    return "".join(parts)


def assert_offline(doc: str) -> int:
    """Grep the rendered document for anything that would reach the network.

    Returns 0 if clean. Called by ``narrate.py`` on the file it just wrote, so
    "self-contained" is an executed check rather than a comment.
    """
    bad = [why for pat, why in _FORBIDDEN if re.search(pat, doc, re.I)]
    if bad:
        print("  HTML OFFLINE CHECK FAILED — rendered document contains: "
              + ", ".join(bad))
        return 1
    return 0
