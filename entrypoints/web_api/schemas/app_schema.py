"""Apps-endpoint response schema."""

from __future__ import annotations

from pydantic import BaseModel

from domain.app import App


class AppResponse(BaseModel):
    slug: str
    name: str
    play_package_name: str | None = None
    apple_bundle_id: str | None = None

    @classmethod
    def from_domain(cls, app: App) -> "AppResponse":
        return cls(
            slug=app.slug,
            name=app.name,
            play_package_name=app.play_package_name,
            apple_bundle_id=app.apple_bundle_id,
        )
