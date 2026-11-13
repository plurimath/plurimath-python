"""Exercise the public roundtrip on actual default-thread subprocess stacks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


def probe(depth):
    import plurimath
    kernel = plurimath.initialize_facade()
    outcome = {"depth": depth, "ok": False}
    try:
        if depth < 256:
            formula = kernel.parse("(" * depth + "x" + ")" * depth, "asciimath")
            formats = ("asciimath", "latex", "unicodemath", "html", "mathml", "omml")
            rendered = {fmt: formula.write(fmt) for fmt in formats}
            if not all(rendered.values()):
                raise AssertionError("Empty rendering of a nonempty formula")
            retained = kernel.from_model(formula.model)
            if retained.model != formula.model or {fmt: retained.write(fmt) for fmt in formats} != rendered:
                raise AssertionError("Native returned model does not roundtrip through its public writers")
            outcome["roundtrip"] = True
        else:
            try:
                kernel.parse("(" * depth + "x" + ")" * depth, "asciimath")
            except plurimath.FacadeError as error:
                if error.code != "resource_limit" or not isinstance(error.details.get("resource"), dict):
                    raise AssertionError("Expected a structured native resource refusal") from error
                outcome["resource"] = error.details["resource"]
            else:
                raise AssertionError("Expected the qualified native parser budget")
        outcome["reuse"] = kernel.parse("1", "asciimath").to_latex() == "1"
        outcome["ok"] = outcome["reuse"]
    except Exception as error:
        outcome["error"] = {"type": type(error).__name__, "details": getattr(error, "details", str(error))}
    print(json.dumps(outcome))
    return 0 if outcome["ok"] else 1


class InstalledDepth(unittest.TestCase):
    def test_public_parse_model_writer_roundtrip_and_resource_reuse(self):
        clean = os.environ.copy()
        for key in ("PYTHONPATH", "PYTHONHOME", "RUST_MIN_STACK", "LD_LIBRARY_PATH", "PARSANOL_LIB"):
            clean.pop(key, None)
        for depth in (16, 64, 128, 256):
            with self.subTest(depth=depth):
                result = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()),
                                         "--native-depth-probe", str(depth)],
                                        capture_output=True, text=True, env=clean, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(json.loads(result.stdout)["ok"])


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--native-depth-probe":
        raise SystemExit(probe(int(sys.argv[2])))
    unittest.main()
