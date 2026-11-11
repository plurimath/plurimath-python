"""Replay the canonical scientific-method wires through the installed facade."""
from contextlib import ExitStack
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import plurimath


class InstalledGum(unittest.TestCase):
    def test_sealed_gum_wires_without_per_request_io(self):
        fixture = json.loads(Path(__file__).with_name("gum-wires.json").read_bytes())
        kernel = plurimath.initialize()
        self.assertIs(plurimath.initialize(), kernel)
        self.assertEqual(len(fixture["cases"]), 73)
        with ExitStack() as guard:
            for name in ("builtins.open", "io.open", "pathlib.Path.open",
                         "pathlib.Path.read_bytes", "pathlib.Path.read_text"):
                guard.enter_context(patch(name, side_effect=AssertionError("request opened a file")))
            guard.enter_context(patch("os.getenv", side_effect=AssertionError("request read environment")))
            guard.enter_context(patch("os._Environ.__getitem__",
                                      side_effect=AssertionError("request read environment")))
            for row in fixture["cases"]:
                with self.subTest(case=row["id"]):
                    self.assertEqual(
                        plurimath.evaluate_json(row["request_json"]),
                        row["expected_wire"],
                    )


if __name__ == "__main__":
    unittest.main()
