from .loader import DatasetSplit, Example, JsonlDataset


def load_jsonl(path: str) -> JsonlDataset:
    return JsonlDataset(path)


__all__ = ["DatasetSplit", "Example", "JsonlDataset", "load_jsonl"]

