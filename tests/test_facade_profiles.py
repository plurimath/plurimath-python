import contextlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import plurimath


class InstalledProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel = plurimath.initialize_facade()
        directory = Path(__file__).parent
        cls.formatters = json.loads((directory / "formatter-reference.json").read_bytes())
        cls.typed = json.loads((directory / "source-values-reference.json").read_bytes())
        cls.contexts = json.loads((directory / "formatter-context-reference.json").read_bytes())

    def test_source_formatter_six_format_bytes(self):
        for row in self.formatters["cases"]:
            formula = self.kernel.from_model(row["model"])
            for fmt, expected in row["expected"].items():
                with self.subTest(id=row["id"], format=fmt):
                    self.assertEqual(formula.write(fmt, formatter_options=row["formatterOptions"]), expected)

    def test_formatter_profiles_composites_and_source_error_envelopes(self):
        for row in self.contexts["cases"]:
            formula = self.kernel.from_model(row["model"])
            for fmt, expected in row["writers"].items():
                with self.subTest(id=row["id"], format=fmt):
                    if "output" in expected:
                        self.assertEqual(formula.write(fmt, formatter_options=row["formatterOptions"]), expected["output"])
                    else:
                        with self.assertRaises(plurimath.FacadeError) as caught:
                            formula.write(fmt, formatter_options=row["formatterOptions"])
                        details = caught.exception.details
                        error = expected["error"]
                        self.assertEqual(details.get("source_class"), error["class"])
                        self.assertEqual(details.get("message"), error["message"])
                        self.assertEqual(details.get("cause", {}).get("source_class"), error["cause_class"])

    def test_native_formatter_refusals_resource_limit_and_reuse(self):
        formula = self.kernel.from_model({"class": "Math::Number", "fields": {"value": "1234"}})
        for settings, code in (({"precision": 1.5}, "unported_capability"),
                               ({"options": {"groupDigits": []}}, "unported_capability"),
                               ({"profile": "imagined"}, "invalid_request"),
                               ({"options": {"groupDigits": 9223372036854775808}}, "resource_limit")):
            with self.subTest(settings=settings):
                with self.assertRaises(plurimath.FacadeError) as caught:
                    formula.to_asciimath(formatter_options=settings)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(formula.to_asciimath(), "1234")

    def test_typed_collision_writers_preserve_source_value_kinds(self):
        for row in self.typed["rows"]:
            formula = self.kernel.from_source_model(row["document"])
            self.assertIsInstance(formula, plurimath.SourceFormula)
            self.assertEqual(formula.source_model, row["document"])
            for fmt, expected in row["writers"].items():
                with self.subTest(id=row["id"], format=fmt):
                    if "output" in expected:
                        self.assertEqual(formula.write(fmt), expected["output"])
                    else:
                        with self.assertRaises(plurimath.FacadeError) as caught:
                            formula.write(fmt)
                        self.assertEqual(caught.exception.details.get("source_class"), expected["error"]["class"])

    def test_initialized_typed_and_formatter_calls_do_not_read_host_state(self):
        source = self.typed["rows"][0]
        formatted = self.formatters["cases"][0]
        with contextlib.ExitStack() as guards:
            for name in ("builtins.open", "io.open", "pathlib.Path.open", "pathlib.Path.read_bytes",
                         "pathlib.Path.read_text", "os.getenv", "os._Environ.__getitem__"):
                guards.enter_context(patch(name, side_effect=AssertionError("per-call I/O")))
            typed = self.kernel.from_source_model(source["document"])
            self.assertEqual(typed.to_mathml(), source["writers"]["mathml"]["output"])
            formula = self.kernel.from_model(formatted["model"])
            self.assertEqual(formula.to_latex(formatter_options=formatted["formatterOptions"]),
                             formatted["expected"]["latex"])

    def test_typed_refusal_release_and_success_reuse(self):
        original = self.kernel._free
        released = []
        def free(pointer):
            released.append(pointer)
            original(pointer)
        self.kernel._free = free
        try:
            document = json.loads(json.dumps(self.typed["rows"][0]["document"]))
            document["root"] = ["unknown-tag"]
            with self.assertRaises(plurimath.FacadeError):
                self.kernel.from_source_model(document)
            self.assertEqual(len(released), 1)
            self.assertEqual(self.kernel.parse("1", "asciimath").to_latex(), "1")
            self.assertEqual(len(released), 3)
        finally:
            self.kernel._free = original


if __name__ == "__main__":
    unittest.main()
