"""Experience buffers for offline learning."""

from .buffer import Experience, ExperienceBuffer


def new_buffer(capacity: int = 1000) -> ExperienceBuffer:
    return ExperienceBuffer(capacity=capacity)


__all__ = ["Experience", "ExperienceBuffer", "new_buffer"]

