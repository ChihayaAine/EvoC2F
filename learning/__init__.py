"""Learning utilities for skill extraction and preference updates."""

from typing import List, Dict, Any

from .learning import Trace, CandidateExtractor, PreferenceLearner

def make_trace(nodes: List[Dict[str, Any]]) -> Trace:
    return Trace(nodes=nodes)


__all__ = ["Trace", "CandidateExtractor", "PreferenceLearner", "make_trace"]

