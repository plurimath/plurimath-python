import contextlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import plurimath


class InstalledFacade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(Path(__file__).with_name("facade-reference.json").read_bytes())
        cls.kernel = plurimath.initialize_facade()

    def test_source_parse_common_model_and_six_writer_bytes(self):
        self.assertTrue(Path(plurimath.__file__).is_relative_to(sys.prefix))
        for row in self.reference["rows"]:
            with self.subTest(row["id"]):
                formula = plurimath.parse(row["input"], row["format"])
                self.assertEqual(formula.model, row["model"])
                for fmt, expected in row["writers"].items():
                    self.assertEqual(formula.write(fmt), expected, fmt)
                    self.assertEqual(getattr(formula, "to_" + fmt)(), expected, fmt)

    def test_canonical_model_roundtrip_snapshot_isolation_and_no_io(self):
        with contextlib.ExitStack() as guard:
            for name in ("builtins.open", "io.open", "pathlib.Path.open", "pathlib.Path.read_bytes",
                         "pathlib.Path.read_text", "os.getenv", "os._Environ.__getitem__"):
                guard.enter_context(patch(name, side_effect=AssertionError("per-call I/O")))
            parsed = plurimath.parse("1", "asciimath")
            self.assertEqual(parsed.to_latex(), "1")
            for row in self.reference["rows"]:
                formula = plurimath.from_model(row["model"])
                self.assertEqual(formula.model, row["model"])
                changed = formula.model
                changed["fields"]["value"].clear()
                self.assertEqual(formula.model, row["model"])
                self.assertEqual(formula.to_latex(), row["writers"]["latex"])

    def test_reply_release_for_success_and_error_then_reuse(self):
        released = []
        original = self.kernel._free
        def release(pointer):
            released.append(True)
            original(pointer)
        self.kernel._free = release
        try:
            with self.assertRaises(plurimath.FacadeError) as refusal:
                self.kernel.request_json("{")
            self.assertEqual(refusal.exception.code, "invalid_json")
            self.assertEqual(len(released), 1)
            formula = self.kernel.parse("1", "asciimath")
            self.assertEqual(len(released), 2)
            self.assertEqual(formula.to_latex(), "1")
            self.assertEqual(len(released), 3)
        finally:
            self.kernel._free = original

    def test_full_source_model_wire_transport(self):
        fixture = json.loads(Path(__file__).with_name("model-transport-reference.json").read_bytes())
        self.assertEqual(len(fixture["rows"]), 646)
        for row in fixture["rows"]:
            with self.subTest(format=row["source_format"], id=row["source_id"]):
                self.assertEqual(self.kernel.from_model(row["model"]).model, row["model"])

    def test_missing_or_wrong_native_component(self):
        native = Path(plurimath.__file__).with_name("_native")
        with self.assertRaises(plurimath.FacadeUnavailableError):
            plurimath.FacadeKernel(native / "missing-facade-library")
        numeric = "plurimath_numeric.dll" if sys.platform == "win32" else "libplurimath_numeric.so"
        with self.assertRaises(plurimath.FacadeUnavailableError):
            plurimath.FacadeKernel(native / numeric)


if __name__ == "__main__":
    unittest.main()
