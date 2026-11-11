"""Evaluate serialized Plurimath AST requests with the bundled Rust kernel."""

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import sys
import sysconfig

from plurimath_numeric import NumericKernel

__all__ = ["NumericKernel", "initialize", "evaluate", "evaluate_json"]


@lru_cache(maxsize=1)
def _kernel():
    directory = Path(__file__).with_name("_native")
    receipt = json.loads((directory / "build-info.json").read_bytes())
    expected = "plurimath_numeric.dll" if sys.platform == "win32" else "libplurimath_numeric.so"
    platform = sysconfig.get_platform().replace("-", "_").replace(".", "_")
    if receipt["abi_version"] != 1 or receipt["library"] != expected or receipt["platform_tag"] != platform:
        raise RuntimeError("Unsupported bundled Plurimath ABI")
    library = directory / receipt["library"]
    if sha256(library.read_bytes()).hexdigest() != receipt["sha256"]:
        raise RuntimeError("Bundled Plurimath library failed its integrity check")
    return NumericKernel(library)


def initialize():
    """Load and verify the bundled kernel before evaluating requests."""
    return _kernel()


def evaluate_json(request):
    """Return the engine's serialized result for a JSON request string."""
    return _kernel().evaluate_json(request)


def evaluate(request):
    """Return the engine's response envelope for a JSON-compatible request."""
    return _kernel().evaluate(request)
