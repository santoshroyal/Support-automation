"""Pydantic response schemas — one file per resource.

Schemas are the contract between the API and the React dashboard. They
take a domain object as input and produce a JSON-friendly dictionary.
Each schema lives in its own file so adding a field doesn't require
touching unrelated resources.
"""
