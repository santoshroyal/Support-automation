"""Cron-driven CLI entrypoints.

Each module exposes a `main()` callable wired in `pyproject.toml` so they
can be invoked either as `python -m entrypoints.cli.<name>` or as the
console script declared there.
"""
