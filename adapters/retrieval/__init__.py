"""Retrieval-augmented generation building blocks.

The drafter never imports anything in here directly; it depends on
KnowledgeRetrieverPort. Hybrid retrieval (vector + lexical), document
chunking, and citation building all live behind that port. Phase-1c
ships chunker + retriever; the citation builder lands with the drafter
in phase-1d.
"""
