import ctypes
import json
from hashlib import sha256
from pathlib import Path
import unittest
from unittest.mock import patch

from plurimath.facade import (FacadeKernel, Formula, SourceFormula,
                              FacadeProtocolError, RUBY_VALUES_PROFILE)


class RecordingKernel:
    def __init__(self):
        self.requests = []

    def request(self, value):
        self.requests.append(value)
        return {"abi_version": 1, "ok": True, "output": "written"}


class PublicAPI(unittest.TestCase):
    def setUp(self):
        self.kernel = RecordingKernel()
        self.model = {"class": "Math::Number", "fields": {"value": "1"}}
        self.formula = Formula._from_reply({"model": self.model}, self.kernel)

    def test_frozen_reference_fixture_bytes(self):
        directory = Path(__file__).parent
        provenance = json.loads((directory / "final-api-provenance.json").read_bytes())
        for fixture in provenance["fixtures"]:
            path = directory.parent / fixture["destination"]
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), fixture["sha256"])

    def test_old_options_and_explicit_formatter_settings(self):
        self.assertEqual(self.formula.write("latex", display_style=False), "written")
        self.assertEqual(self.kernel.requests[-1]["options"], {"display_style": False})
        for settings in (None, False, {"profile": "base", "localizerSymbols": {"group": " "}}):
            self.formula.to_latex(formatter_options=settings)
            self.assertEqual(self.kernel.requests[-1]["options"], {"formatterOptions": settings})
        with self.assertRaises(TypeError):
            self.formula.write("latex", formatter_options={}, formatterOptions={})

    def test_source_document_profile_is_explicit_and_isolated(self):
        document = {"schema": RUBY_VALUES_PROFILE, "producer": {"source_commit": "assertion"},
                    "root": ["node", "Math::Number", [["value", ["symbol", "x"]]]]}
        formula = SourceFormula._from_reply({"model": document}, self.kernel)
        self.assertEqual(formula.source_profile, RUBY_VALUES_PROFILE)
        snapshot = formula.source_model
        snapshot["root"].clear()
        self.assertEqual(formula.source_model, document)
        formula.to_mathml(formatter_options=False)
        request = self.kernel.requests[-1]
        self.assertEqual(request["source_profile"], RUBY_VALUES_PROFILE)
        self.assertEqual(request["model"], document)
        self.formula.to_mathml()
        self.assertNotIn("source_profile", self.kernel.requests[-1])

    def test_kernel_source_model_operation_is_native_validated(self):
        document = {"schema": RUBY_VALUES_PROFILE, "producer": {},
                    "root": ["node", "Math::Number", []]}
        kernel = FacadeKernel.__new__(FacadeKernel)
        with patch.object(kernel, "request", return_value={"model": document}) as request:
            formula = kernel.from_source_model(document)
        request.assert_called_once_with({"op": "source_model", "model": document})
        self.assertEqual(formula.source_model, document)

    def test_invalid_source_reply_is_protocol_error(self):
        for document in (None, {}, self.model):
            with self.assertRaises(FacadeProtocolError):
                SourceFormula._from_reply({"model": document}, self.kernel)

    def test_native_reply_freed_before_malformed_reply_refusal(self):
        kernel = FacadeKernel.__new__(FacadeKernel)
        for data in (b"not-json", b"{}", b'{"abi_version":true,"ok":true}'):
            buffer = ctypes.create_string_buffer(data)
            pointer = ctypes.addressof(buffer)
            freed = []
            kernel._request = lambda *args: pointer
            kernel._free = freed.append
            with self.assertRaises(FacadeProtocolError):
                kernel.request_json("{}")
            self.assertEqual(freed, [pointer])
        kernel._request = lambda *args: None
        kernel._free = lambda *args: self.fail("NULL must not be freed")
        with self.assertRaises(FacadeProtocolError):
            kernel.request_json("{}")


if __name__ == "__main__":
    unittest.main()
