"""Protocol forwarding only: these mocks do not qualify native PMA semantics."""
import unittest
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch
from plurimath import FacadeError, FacadeKernel


class PMAForwarding(unittest.TestCase):
    def test_frozen_core_reference_bytes_and_actual_outcomes(self):
        root = Path(__file__).resolve().parents[1]
        feature = json.loads((root / "features/pma-v1.json").read_bytes())
        raw = (root / feature["source_reference"]["path"]).read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), feature["source_reference"]["sha256"])
        rows = json.loads(raw)["rows"]
        self.assertEqual(sum("model" in row for row in rows), 34)
        self.assertEqual(sum("refusal" in row for row in rows), 64)

    def test_pma_text_and_empty_options_reach_native_unchanged(self):
        kernel = FacadeKernel.__new__(FacadeKernel)
        opaque_model = {"class": "Math::Formula", "fields": {"value": []}}
        text = "ustd(1.230, 0.004)"
        with patch.object(kernel, "request", return_value={"model": opaque_model}) as request:
            formula = kernel.parse(text, "pma")
        request.assert_called_once_with({"op": "parse", "format": "pma", "input": text, "options": {}})
        self.assertEqual(formula.model, opaque_model)

    def test_options_and_native_refusal_are_not_rewritten_by_python(self):
        kernel = FacadeKernel.__new__(FacadeKernel)
        refusal = FacadeError({"code": "PARSE_OPTION_ERROR", "message": "native rejection"})
        with patch.object(kernel, "request", side_effect=refusal) as request:
            with self.assertRaises(FacadeError) as caught:
                kernel.parse("ustd(1.230, 0.004)", "pma", locale="fr", decimal=",")
        self.assertIs(caught.exception, refusal)
        self.assertEqual(request.call_args.args[0]["options"], {"locale": "fr", "decimal": ","})


if __name__ == "__main__":
    unittest.main()
