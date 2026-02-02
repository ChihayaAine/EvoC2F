from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional


LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


@dataclass
class LoggerConfig:
    name: str
    level: int = logging.INFO
    logfile: Optional[str] = None
    propagate: bool = False
    fmt: str = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"


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
        level = LEVEL_MAP.get(env_level.lower(), level)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(LoggerConfig(name=name).fmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    if logfile:
        file_handler = logging.FileHandler(logfile)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    logger.propagate = propagate
    return logger


def get_logger(name: str, config: Optional[LoggerConfig] = None) -> logging.Logger:
    config = config or LoggerConfig(name=name)
    return setup_logger(
        name=config.name,
        level=config.level,
        logfile=config.logfile,
        propagate=config.propagate,
    )


def configure_root(level: Optional[str] = None) -> None:
    if level is None:
        level = os.getenv("EVOC2F_LOG_LEVEL", "info")
    logging.basicConfig(level=LEVEL_MAP.get(level.lower(), logging.INFO))


def log_context(logger: logging.Logger, message: str, context: Dict[str, object]) -> None:
    suffix = " ".join(f"{k}={v}" for k, v in context.items())
    logger.info("%s %s", message, suffix)

