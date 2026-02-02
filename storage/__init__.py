from .json_store import JsonStore

def open_store(path: str) -> JsonStore:
    return JsonStore(path)


__all__ = ["JsonStore", "open_store"]

