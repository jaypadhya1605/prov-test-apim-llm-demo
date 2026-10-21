import unittest

from tools.verify_reference import MODEL_CORRELATION, verify


class PublicReferenceTests(unittest.TestCase):
    def test_model_identifiers_require_public_alias_marker(self):
        self.assertIsNotNone(MODEL_CORRELATION.search("resp_" + "a" * 32))
        self.assertIsNone(MODEL_CORRELATION.search("resp_example-" + "a" * 24))

    def test_complete_snapshot_passes_offline_integrity_and_publication_checks(self):
        issues, summary = verify()
        self.assertEqual(issues, [])
        self.assertEqual(summary["evidenceFiles"], 740)
        self.assertEqual(summary["callRecords"], 205)


if __name__ == "__main__":
    unittest.main()
