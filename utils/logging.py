from __future__ import annotations

import logging
import os
from typing import Optional


def setup_logger(
    name: str,
    level: int = logging.INFO,
    logfile: Optional[str] = None,
    propagate: bool = False,
) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    env_level = os.getenv("EVOC2F_LOG_LEVEL")
    if env_level:
        level = getattr(logging, env_level.upper(), level)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    if logfile:
        file_handler = logging.FileHandler(logfile)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    logger.propagate = propagate
    return logger

