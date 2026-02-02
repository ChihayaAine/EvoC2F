from .learning import Trace, CandidateExtractor, PreferenceLearner

def make_trace(nodes):
    return Trace(nodes=nodes)


__all__ = ["Trace", "CandidateExtractor", "PreferenceLearner", "make_trace"]

