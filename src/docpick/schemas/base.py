"""Base schema class and registry."""

from __future__ import annotations

from pydantic import BaseModel


class DocumentSchema(BaseModel):
    """Base class for all document schemas.

    Subclass this to define custom document extraction schemas.
    Schemas registered via the registry can be referenced by name in CLI.
    """

    model_config = {"extra": "allow"}


class SchemaRegistry:
    """Registry for built-in and custom document schemas."""

    def __init__(self) -> None:
        self._schemas: dict[str, type[DocumentSchema]] = {}

    def register(self, name: str, schema: type[DocumentSchema]) -> None:
        self._schemas[name] = schema

    def get(self, name: str) -> type[DocumentSchema]:
        if name not in self._schemas:
            available = ", ".join(sorted(self._schemas.keys()))
            raise KeyError(f"Unknown schema: '{name}'. Available: {available}")
        return self._schemas[name]

    def list(self) -> dict[str, type[DocumentSchema]]:
        return dict(self._schemas)

    def names(self) -> list[str]:
        return sorted(self._schemas.keys())


# Global registry instance
schema_registry = SchemaRegistry()
