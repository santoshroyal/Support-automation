"""HTTP route handlers — one module per resource.

Each module exposes a `router` instance that `main.py` mounts into the
app. Routes are thin: they pull what they need via `Depends()`, call
ports, and convert domain objects to Pydantic schemas. No business
logic lives here.
"""
