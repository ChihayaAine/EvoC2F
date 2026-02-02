"""Storage adapters."""

from .json_store import JsonStore, StoreConfig


def open_store(path: str, config: StoreConfig | None = None) -> JsonStore:
    return JsonStore(path, config=config)


__all__ = ["JsonStore", "StoreConfig", "open_store"]

