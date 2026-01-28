# Models

Model adapters, checkpoints, and training helpers can be organized here.

Recommended structure:
- `base.py`: base interfaces and request/response types
- `stub.py`: local stub for testing
- `adapters/`: provider-specific wrappers

Model implementations should return `ModelResponse` and populate token counts.

