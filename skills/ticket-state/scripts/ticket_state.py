#!/usr/bin/env python3
"""Portable command-line entry point for ticket-state."""

from __future__ import annotations

from ticket_state.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
