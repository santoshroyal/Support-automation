"""Language-model adapters — implementations of LanguageModelPort.

Phase-1 ships four:

  * RecordedResponseLanguageModel — looks up canned responses by prompt hash.
    Used by tests and CI; works with no external tools installed.
  * ClaudeCodeLanguageModel       — subprocess `claude -p`. Uses the user's
    terminal Claude Code subscription.
  * CodexCliLanguageModel         — subprocess `codex exec`. Uses the user's
    terminal Codex subscription.
  * OllamaGemmaLanguageModel      — HTTP POST to localhost:11434, fully local.

A small router (LanguageModelRouter) picks one based on settings and falls
back if the primary is unhealthy. This module is the only place in the
codebase that runs subprocesses or makes outbound HTTP calls for language
model inference.
"""
