import unittest

from ui.widgets.settings.receipt_config import merge_receipt_config


class ReceiptConfigCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.defaults = {
            "paper_width_mm": 80.0,
            "header": {"show": True, "text": "Header"},
            "logo": {"show": True, "path": "", "align": "center"},
            "barcode": {"show": True, "height_mm": 10.0},
        }

    def test_legacy_template_gets_missing_logo_and_nested_defaults(self):
        result = merge_receipt_config(self.defaults, {"header": {"text": "Old"}})

        self.assertEqual(result["header"]["text"], "Old")
        self.assertTrue(result["logo"]["show"])
        self.assertEqual(result["barcode"]["height_mm"], 10.0)

    def test_invalid_nested_value_cannot_remove_required_schema(self):
        result = merge_receipt_config(self.defaults, {"logo": None})

        self.assertIsInstance(result["logo"], dict)
        self.assertTrue(result["logo"]["show"])

    def test_unknown_keys_are_preserved_without_mutating_inputs(self):
        saved = {"custom": {"enabled": True}, "logo": {"path": "logo.png"}}
        result = merge_receipt_config(self.defaults, saved)

        self.assertEqual(result["custom"], {"enabled": True})
        self.assertEqual(result["logo"]["path"], "logo.png")
        self.assertNotIn("custom", self.defaults)
        self.assertEqual(saved["logo"], {"path": "logo.png"})


if __name__ == "__main__":
    unittest.main()
