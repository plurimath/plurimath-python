"""Source-frozen PMA common-model/writer contract; requires the new sealed core."""
from hashlib import sha256
import json
from pathlib import Path
import unittest
import plurimath


class InstalledPMA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel = plurimath.initialize_facade()
        cls.reference = json.loads(Path(__file__).with_name("pma-core-reference.json").read_bytes())

    def test_all_observed_ruby_core_outcomes_and_six_writers(self):
        accepted = refused = outputs = 0
        for row in self.reference["rows"]:
            with self.subTest(id=row["id"]):
                if "model" in row:
                    formula = self.kernel.parse(row["input"], "pma")
                    self.assertEqual(formula.model, row["model"])
                    accepted += 1
                    for fmt, expected in row["writers"].items():
                        self.assertEqual(formula.write(fmt), expected["output"], fmt)
                        outputs += 1
                else:
                    with self.assertRaises(plurimath.FacadeError) as caught:
                        self.kernel.parse(row["input"], "pma")
                    self.assertEqual(caught.exception.code, "PARSE_ERROR")
                    self.assertEqual(caught.exception.details.get("source_class"), row["refusal"]["error"])
                    refused += 1
        self.assertEqual((accepted, refused, outputs), (34, 64, 204))

    def test_pma_parse_options_refused_then_reuse(self):
        for options in ({"locale": "fr"}, {"decimal": ","}):
            with self.assertRaises(plurimath.FacadeError) as caught:
                self.kernel.parse("ustd(1.230, 0.004)", "pma", **options)
            self.assertEqual(caught.exception.code, "PARSE_OPTION_ERROR")
        self.assertEqual(self.kernel.parse("ustd(1.230, 0.004)", "pma").to_asciimath(), "ustd(1.230, 0.004)")


if __name__ == "__main__":
    unittest.main()
