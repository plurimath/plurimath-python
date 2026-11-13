"""Read frozen producer bytes; called by both source and installed corpus checks."""
import gzip
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "corpus"


def load(name):
    manifest = json.loads((ROOT / "provenance.json").read_bytes())
    receipt = manifest["files"][name]
    packed = (ROOT / name).read_bytes()
    if sha256(packed).hexdigest() != receipt["sha256"]:
        raise AssertionError("Frozen corpus compressed bytes changed: " + name)
    raw = gzip.decompress(packed)
    if sha256(raw).hexdigest() != receipt["uncompressed_sha256"]:
        raise AssertionError("Frozen producer bytes changed: " + name)
    return json.loads(raw)
