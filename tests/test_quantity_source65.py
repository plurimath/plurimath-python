"""Installed source65 quantity packet (strict38 subset) and warmed no-IO public calls."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class InstalledQuantitySource65(unittest.TestCase):
    def test_source65_strict38_and_warmed_public_calls_without_io(self):
        helper = Path(__file__).with_name("installed_source65_child.py").resolve()
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-I", str(helper)], cwd=directory,
                                    capture_output=True, text=True, timeout=900)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["cases"], 65)
        self.assertEqual(report["counts"], {"accepted": 62, "refusals": 3, "tagged": 33,
                                            "legacy": 29, "float_bits": 8, "strict38": 38})
        self.assertEqual(report["warmed_forbidden_events"], [])


if __name__ == "__main__":
    unittest.main()
