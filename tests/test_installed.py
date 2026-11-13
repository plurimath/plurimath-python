import json
from pathlib import Path
import unittest

import plurimath


class InstalledEvaluation(unittest.TestCase):
    def test_numeric_reference_wires(self):
        for path in sorted(Path(__file__).parent.glob("numeric-*.json")):
            fixture = json.loads(path.read_bytes())
            for row in fixture["cases"]:
                with self.subTest(profile=path.stem, case=row["id"]):
                    if "request_json" in row:
                        self.assertEqual(plurimath.evaluate_json(row["request_json"]), row["expected_wire"])
                    else:
                        request = json.dumps(row["request"], ensure_ascii=False, separators=(",", ":"))
                        self.assertEqual(plurimath.evaluate_json(request), row["expected_wire"])
                        self.assertEqual(plurimath.evaluate(row["request"]), json.loads(row["expected_wire"]))

    def test_wire_refusal_then_reuse(self):
        refusal = json.loads(plurimath.evaluate_json("{"))
        self.assertIs(refusal["ok"], False)
        self.assertEqual(refusal["error"]["code"], "InvalidRequest")
        fixture = json.loads(Path(__file__).with_name("numeric-v1.json").read_bytes())
        first = fixture["cases"][0]
        self.assertEqual(plurimath.evaluate(first["request"]), json.loads(first["expected_wire"]))


if __name__ == "__main__":
    unittest.main()
