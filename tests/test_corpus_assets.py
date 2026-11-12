import unittest
from corpus_assets import load


class FrozenCorpusTests(unittest.TestCase):
    def test_source_ids_counts_and_options_remain_present(self):
        rows = load("writer-reference-2928.json.gz")["rows"]
        self.assertEqual(len(rows), 2928)
        self.assertEqual(sum("model" in r["case"]["input"] for r in rows), 2070)
        self.assertEqual(len({(r["output_format"], r["case"]["id"]) for r in rows}), 2928)
        text = load("ruby-full-text-oracle.json.gz")["rows"]
        self.assertEqual(sum(len(r["writers"]) for r in text), 870)
        self.assertEqual(len(load("parser-jobs.json.gz")["jobs"]), 1349)
