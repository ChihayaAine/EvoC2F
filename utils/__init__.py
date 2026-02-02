from .math import cosine_similarity, MLP
from .logging import setup_logger
from .serialization import JsonSerializer

def json_dumps(payload) -> str:
    return JsonSerializer().dumps(payload)


def json_loads(payload: str):
    return JsonSerializer().loads(payload)


__all__ = [
    "cosine_similarity",
    "MLP",
    "setup_logger",
    "JsonSerializer",
    "json_dumps",
    "json_loads",
]

