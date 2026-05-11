"""Inbound feedback channels — one adapter per channel, two flavours per channel.

Real adapters (e.g. `gmail_feedback_source.py`) call the live API.
Local adapters (`local_*.py`) read from `data_fixtures/` so the system runs
end-to-end with no real credentials.
"""
