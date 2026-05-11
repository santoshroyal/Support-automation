"""Knowledge sources — implementations of KnowledgeSourcePort.

Two flavours per source:

  * Real adapters (`confluence_knowledge_source.py`, …) call the live API
    using credentials in `secrets/`.
  * Local adapters (`local_*_knowledge_source.py`) read fixture files from
    `data_fixtures/knowledge/<source>/` so the system can sync end-to-end
    without any real credentials. CI uses these.
"""
