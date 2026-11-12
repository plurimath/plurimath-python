"""Strict actual source outputs/classes, without accepted native-refusal baselines."""
import unittest
from corpus_assets import load
from plurimath import FacadeError, initialize_facade


class FullInstalledFacadeCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel = initialize_facade()

    def setUp(self):
        self.requests = 0
        self.frees = 0
        self.original_request = self.kernel._request
        self.original_free = self.kernel._free
        def request(*args):
            self.requests += 1
            return self.original_request(*args)
        def free(pointer):
            self.frees += 1
            return self.original_free(pointer)
        self.kernel._request = request
        self.kernel._free = free

    def tearDown(self):
        self.kernel._request = self.original_request
        self.kernel._free = self.original_free
        self.assertGreater(self.requests, 0)
        self.assertEqual(self.requests, self.frees)

    def check_writer(self, construct, output_format, options, expected):
        if "output" in expected:
            self.assertEqual(construct().write(output_format, **options), expected["output"])
        else:
            source_class = (expected.get("source_class") or expected.get("error", {}).get("class")
                            or expected.get("error", {}).get("class_"))
            self.assertIsInstance(source_class, str)
            with self.assertRaises(FacadeError) as refusal:
                construct().write(output_format, **options)
            self.assertEqual(refusal.exception.details.get("source_class"), source_class)

    def test_original_model_and_parse_writer_option_rows(self):
        for row in load("writer-reference-2928.json.gz")["rows"]:
            case = row["case"]
            with self.subTest(id=case["id"], format=row["output_format"]):
                source = case["input"]
                def construct():
                    if "model" in source:
                        return self.kernel.from_model(source["model"])
                    return self.kernel.parse(source["text"], source["format"])
                expected = ({"output": case["expected"]} if "expected" in case
                            else {"error": {"class": case.get("raises")}})
                self.check_writer(construct, row["output_format"], case.get("options", {}), expected)

    def test_current_source_text_models_through_all_writers(self):
        for row in load("ruby-full-text-oracle.json.gz")["rows"]:
            model = row.get("parsed_model", row.get("model"))
            for output_format, source in row["writers"].items():
                with self.subTest(id=row["id"], format=output_format):
                    expected = {"output": source} if isinstance(source, str) else source
                    self.check_writer(lambda: self.kernel.from_model(model), output_format, {}, expected)

    def test_full_source_parser_models_and_refusals(self):
        for job in load("parser-jobs.json.gz")["jobs"]:
            with self.subTest(id=job["id"], format=job["format"]):
                if "model" in job:
                    self.assertEqual(self.kernel.parse(job["input"], job["format"],
                                     **job.get("options", {})).model, job["model"])
                else:
                    with self.assertRaises(FacadeError) as refusal:
                        self.kernel.parse(job["input"], job["format"], **job.get("options", {}))
                    self.assertEqual(refusal.exception.code, "PARSE_ERROR")
