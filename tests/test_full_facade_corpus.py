"""Strict actual source outputs/classes, without accepted native-refusal baselines."""
from hashlib import sha256
import json
from pathlib import Path
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

    def source_corrections(self):
        """Measured Ruby 0a1df68 corrections, applied only to byte-identical legacy rows."""
        folder = Path(__file__).parent / "fixtures" / "source-profile-ruby0a1"
        receipt = json.loads((folder / "source.json").read_bytes())
        payload = (folder / "cases.json").read_bytes()
        self.assertEqual(sha256(payload).hexdigest(), receipt["sha256"])
        profile = json.loads(payload)
        self.assertEqual(profile["schema"], "plurimath.facade-source-profile/1")
        packed = (Path(__file__).parent / "corpus" / "writer-reference-2928.json.gz").read_bytes()
        self.assertEqual(sha256(packed).hexdigest(), profile["legacy"]["writer_corpus_sha256"])
        corrections = {(row["id"], row["format"]): row for row in profile["corrections"]}
        self.assertEqual(len(corrections), len(profile["corrections"]))
        self.assertEqual(len(corrections), 1)
        return corrections

    def test_original_model_and_parse_writer_option_rows(self):
        corrections = self.source_corrections()
        applied = set()
        rows = load("writer-reference-2928.json.gz")["rows"]
        self.assertEqual(len(rows), 2928)
        for row in rows:
            case = row["case"]
            with self.subTest(id=case["id"], format=row["output_format"]):
                source = case["input"]
                def construct():
                    if "model" in source:
                        return self.kernel.from_model(source["model"])
                    if "parseOptions" in case:
                        return self.kernel.parse(source["text"], source["format"],
                                                 parse_options=case["parseOptions"])
                    return self.kernel.parse(source["text"], source["format"])
                expected = ({"output": case["expected"]} if "expected" in case
                            else {"error": {"class": case.get("raises")}})
                correction = corrections.get((case["id"], row["output_format"]))
                if correction is not None:
                    encoded = json.dumps(case, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=False).encode()
                    self.assertEqual(sha256(encoded).hexdigest(), correction["legacy_case_sha256"])
                    self.assertEqual(case, correction["legacy_case"])
                    self.assertEqual(case["input"], correction["input"])
                    self.assertEqual(case.get("options", {}), correction["options"])
                    self.assertIsInstance(correction["expected_output"], str)
                    expected = {"output": correction["expected_output"]}
                    applied.add((case["id"], row["output_format"]))
                self.check_writer(construct, row["output_format"], case.get("options", {}), expected)
        self.assertEqual(applied, set(corrections), "every source correction must apply; no waiver")

    def test_current_source_text_models_through_all_writers(self):
        rows = load("ruby-full-text-oracle.json.gz")["rows"]
        self.assertEqual(sum(len(row["writers"]) for row in rows), 3798 - 2928)
        for row in rows:
            model = row.get("parsed_model", row.get("model"))
            for output_format, source in row["writers"].items():
                with self.subTest(id=row["id"], format=output_format):
                    expected = {"output": source} if isinstance(source, str) else source
                    self.check_writer(lambda: self.kernel.from_model(model), output_format, {}, expected)

    def test_full_source_parser_models_and_refusals(self):
        references = json.loads((Path(__file__).parent / "fixtures" /
                                 "parser-negative23-public-ruby.json").read_bytes())["rows"]
        source_errors = {row["id"]: row for row in references}
        self.assertEqual(len(source_errors), 23)
        jobs = load("parser-jobs.json.gz")["jobs"]
        self.assertEqual(len(jobs), 1349)
        for job in jobs:
            with self.subTest(id=job["id"], format=job["format"]):
                if "model" in job:
                    self.assertEqual(self.kernel.parse(job["input"], job["format"],
                                     **job.get("options", {})).model, job["model"])
                else:
                    with self.assertRaises(FacadeError) as refusal:
                        self.kernel.parse(job["input"], job["format"], **job.get("options", {}))
                    self.assertEqual(refusal.exception.code, "PARSE_ERROR")
                    source = source_errors[job["id"]]
                    self.assertEqual(source["input"], {"format": job["format"], "text": job["input"]})
                    self.assertEqual(refusal.exception.details.get("source_class"), source["parse_error"]["class"])
