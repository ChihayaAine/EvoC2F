from .tracker import MetricTracker

def new_tracker() -> MetricTracker:
    return MetricTracker()


__all__ = ["MetricTracker", "new_tracker"]

