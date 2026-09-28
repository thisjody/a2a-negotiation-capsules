#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline proof: run the whole demo with the socket layer bricked.

Not a claim in a README — an executed test. Every entry point that could open
a connection (``socket.socket``, ``socket.create_connection``,
``socket.getaddrinfo``, ``ssl.SSLContext.wrap_socket``) is replaced with a
function that raises. The narrator then runs end to end.

If any part of the demo — the emitter, the witness/anchor path, the AAuth
stub, the negotiation front-half, the cross-verifier, the ``--html`` render
— reached for the network, this test fails with the traceback
pointing at the caller.

The run is driven with ``--fast --html``: ``--fast`` because the narrated
pauses are pure ``time.sleep`` and a 90-second test is a test nobody runs, and
``--html`` because the browser render is exactly the sort of thing that grows
a CDN link, so the offline claim about it is checked here too.

    python test_offline.py
"""
from __future__ import annotations

import socket
import ssl
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


class EgressAttempted(RuntimeError):
    pass


def _brick(name):
    def _raise(*a, **k):
        raise EgressAttempted(
            f"{name} was called — this demo must not touch the network"
        )
    return _raise


def main() -> int:
    socket.socket = _brick("socket.socket")
    socket.create_connection = _brick("socket.create_connection")
    socket.getaddrinfo = _brick("socket.getaddrinfo")
    ssl.SSLContext.wrap_socket = _brick("ssl.SSLContext.wrap_socket")

    bundle = Path(tempfile.mkdtemp(prefix="demo2-offline-"))
    import narrate

    old = sys.argv
    # --fast: the narrated pauses are timing only and never open a socket, but
    # a test that sleeps ~90 s to prove a negative is a test nobody runs. The
    # pacing path is still exercised (Pace is constructed and every beat() is
    # called); only the sleep is zero.
    sys.argv = ["narrate.py", "--bundle", str(bundle), "--fast", "--html"]
    try:
        rc = narrate.main()
    except EgressAttempted as e:
        print(f"\nFAIL — {e}")
        return 1
    finally:
        sys.argv = old

    print(f"\ntest_offline: narrate.main() returned {rc} with the socket layer bricked.")
    print("test_offline: PASS — no network call was attempted anywhere in the run."
          if rc == 0 else "test_offline: FAIL — narrate reported a failure.")
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
