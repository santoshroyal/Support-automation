"""Embedding-model adapters — implementations of EmbeddingModelPort.

Phase-1 ships one: a local sentence-transformer running multilingual-e5-base.
CPU-only. No network access at inference time. The model file is downloaded
once on first use (cached under ~/.cache/huggingface/) and reused thereafter.
"""
