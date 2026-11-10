"""Evaluate serialized Plurimath AST requests with the bundled Rust kernel."""

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from plurimath_numeric import NumericKernel

__all__ = ["NumericKernel", "evaluate", "evaluate_json"]


@lru_cache(maxsize=1)
def _kernel():
    directory = Path(__file__).with_name("_native")
    receipt = json.loads((directory / "build-info.json").read_bytes())
    if receipt["abi_version"] != 1 or receipt["library"] != "libplurimath_numeric.so":
        raise RuntimeError("Unsupported bundled Plurimath ABI")
    library = directory / receipt["library"]
    if sha256(library.read_bytes()).hexdigest() != receipt["sha256"]:
        raise RuntimeError("Bundled Plurimath library failed its integrity check")
    return NumericKernel(library)


def evaluate_json(request):
    """Return the engine's serialized result for a JSON request string."""
    return _kernel().evaluate_json(request)


def evaluate(request):
    """Return the engine's response envelope for a JSON-compatible request."""
    return _kernel().evaluate(request)
