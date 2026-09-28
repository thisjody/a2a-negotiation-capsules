#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Pacing for the narrated beats — timing only, never a socket.

The negotiation front-half is meant to be *watched*, not scrolled past. A
narrated move that prints its reasoning line and its action line in the same
instant reads as a log dump; the same two lines with a beat between them read
as a haggle. That is the whole job of this module.

Three modes, and the mode is the only thing that changes:

``pause`` (default)
    ``time.sleep(delay)`` between beats, 1.2 s by default. A watcher reads
    each move before the next one lands.

``step`` (``--step``)
    Wait for Enter between beats, so a presenter drives the pace live. If
    stdin is not a terminal (piped, CI, ``test_offline.py``) the wait would
    hit EOF immediately and, worse, could hang a headless runner — so this
    mode **degrades to** ``fast`` the moment it sees a non-interactive stdin
    or an EOF. A demo that cannot hang is worth more than a demo that always
    waits.

``fast`` (``--fast``, ``FAST=1``, or a non-TTY stdout)
    No pause at all. This is what ``test_offline.py``, CI and the transcript
    regeneration use, so they stay instant.

**These pauses never open a socket.** ``time.sleep`` and ``input`` are the
only calls here; ``test_offline.py`` runs the whole demo with the socket layer
bricked and this module is on that path.
"""
from __future__ import annotations

import os
import sys
import time

MODES = ("pause", "step", "fast")

DEFAULT_DELAY = 1.2


class Pace:
    """A beat between narrated moves.

    ``Pace.beat()`` is the only thing callers need. Everything else is the
    mode resolution, which is deliberately explicit so the presenter runbook
    can state exactly what will happen on a given machine.
    """

    def __init__(self, mode: str = "pause", delay: float = DEFAULT_DELAY) -> None:
        if mode not in MODES:
            raise ValueError(f"pace mode must be one of {MODES}, got {mode!r}")
        self.delay = max(0.0, float(delay))
        self.mode = mode
        self.degraded_reason: str | None = None
        if mode == "step" and not sys.stdin.isatty():
            self.mode = "fast"
            self.degraded_reason = "--step asked for, but stdin is not a terminal"
        if self.mode == "pause" and self.delay == 0.0:
            self.mode = "fast"

    # -- construction from the command line ---------------------------------

    @classmethod
    def from_args(cls, *, fast: bool, step: bool, delay: float,
                  delay_was_explicit: bool = False) -> "Pace":
        """Resolve the mode from the flags, the environment and the terminal.

        Precedence, highest first:

        1. ``--fast`` or ``FAST=1``  -> ``fast``
        2. ``--step``                -> ``step`` (degrades to ``fast`` off a TTY)
        3. stdout is not a TTY and no explicit ``--pace`` -> ``fast``
        4. otherwise                 -> ``pause`` at ``delay`` seconds

        Rule 3 is why ``python narrate.py > transcript.txt`` is instant: a run
        nobody is watching should not sit there sleeping.
        """
        if fast or os.environ.get("FAST", "") not in ("", "0", "false", "no"):
            return cls("fast", delay)
        if step:
            return cls("step", delay)
        if not sys.stdout.isatty() and not delay_was_explicit:
            p = cls("fast", delay)
            p.degraded_reason = "stdout is not a terminal, so pauses are off"
            return p
        return cls("pause", delay)

    # -- the beat ------------------------------------------------------------

    def beat(self, n: float = 1.0) -> None:
        """Hold for one beat (``n`` scales it — 0.5 for a half beat).

        Never raises. A Ctrl-C at a ``--step`` prompt drops the rest of the
        run to ``fast`` rather than killing the demo mid-sentence.
        """
        if self.mode == "fast":
            return
        if self.mode == "step":
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                self.mode = "fast"
                self.degraded_reason = "step prompt hit EOF/interrupt; pauses off"
            return
        try:
            time.sleep(self.delay * n)
        except KeyboardInterrupt:
            self.mode = "fast"
            self.degraded_reason = "interrupted; pauses off"

    def describe(self) -> str:
        """One line for the demo header, so the room knows what to expect."""
        if self.mode == "fast":
            base = "fast (no pauses)"
        elif self.mode == "step":
            base = "step (press Enter between beats)"
        else:
            base = f"pause ({self.delay:g}s between narrated beats)"
        return base + (f" — {self.degraded_reason}" if self.degraded_reason else "")
