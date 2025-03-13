import pytest

has_enhanced_serializer: bool = False
try:
    import pydantic_enhanced_serializer  # noqa: F401
    has_enhanced_serializer = True
except ImportError:
    pass


require_serializer = pytest.mark.skipif(
    not has_enhanced_serializer,
    reason="Requires pydantic_enhanced_serializer"
)
