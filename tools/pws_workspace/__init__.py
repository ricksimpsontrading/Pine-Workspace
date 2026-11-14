# SPDX-License-Identifier: Apache-2.0
"""pws_workspace — deterministic local tooling for Pine Workspace.

Mechanical facts only: filesystem, local Git, JSON, hashes, structure,
simple headers, mechanically forbidden strings, validation state, standard
state. No semantic judgement (signal quality, UX, repaint, correctness).

Launcher: python3 -m tools.pws_workspace <subcommand>
"""

__all__ = [
    "core",
    "scan",
    "standard",
    "guard",
    "validation",
    "tv_mode",
    "session",
    "doctor",
]
