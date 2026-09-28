#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""In-process 'wire' between the two agents — no network, no transport, no LLM.

Every A2A message the demo would send over JSON-RPC is instead handed to
:class:`Wire`, which prints the frame as JSON and keeps it for the transcript.
The point of showing the frames is that a skeptic can see exactly what one
agent told the other, and then check that the *record* commits to that and
nothing more.

Redaction rule (load-bearing, not cosmetic)
-------------------------------------------
The bearer token really does cross the wire — that is what a bearer token is
for. It is printed as a shape summary, never verbatim, because the demo is
routinely screen-shared. The important claim is the stronger one, and it is
checked mechanically in ``crossverify.py``: **the raw token never enters a
capsule or a ledger.**
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

TOKEN_KEYS = {"access_token", "authorization", "bearer_token", "token"}


def redact(payload: Any) -> Any:
    """Replace any bearer-token value with a shape summary."""
    if isinstance(payload, dict):
        out = {}
        for k, v in payload.items():
            if k in TOKEN_KEYS and isinstance(v, str) and v.count(".") == 2:
                segs = v.split(".")
                out[k] = (
                    f"<redacted compact JWS: 3 segments, "
                    f"{len(segs[0])}.{len(segs[1])}.{len(segs[2])} chars, "
                    f"{len(v)} bytes total>"
                )
            else:
                out[k] = redact(v)
        return out
    if isinstance(payload, list):
        return [redact(v) for v in payload]
    return payload


@dataclass
class Frame:
    seq: int
    sender: str
    recipient: str
    kind: str
    payload: dict


@dataclass
class Wire:
    """Records and prints frames. In-process only — nothing opens a socket."""

    frames: list[Frame] = field(default_factory=list)
    quiet: bool = False

    def send(self, sender: str, recipient: str, kind: str, payload: dict) -> dict:
        frame = Frame(len(self.frames) + 1, sender, recipient, kind, payload)
        self.frames.append(frame)
        if not self.quiet:
            envelope = {
                "seq": frame.seq,
                "from": sender,
                "to": recipient,
                "kind": kind,
                "payload": redact(payload),
            }
            print("    wire " + json.dumps(envelope, sort_keys=True, separators=(",", ": ")))
        return payload

    def as_json(self) -> list[dict]:
        return [
            {
                "seq": f.seq,
                "from": f.sender,
                "to": f.recipient,
                "kind": f.kind,
                "payload": redact(f.payload),
            }
            for f in self.frames
        ]
