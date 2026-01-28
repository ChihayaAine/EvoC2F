from .buffer import ExperienceBuffer

def new_buffer(capacity: int = 1000) -> ExperienceBuffer:
    return ExperienceBuffer(capacity=capacity)


__all__ = ["ExperienceBuffer", "new_buffer"]

