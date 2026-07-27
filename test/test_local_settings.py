import json
import os
import tempfile
import unittest

from ui.widgets.settings.local_settings import LocalSettingsStore


class LocalSettingsStoreTests(unittest.TestCase):
    def test_users_have_independent_general_settings(self):
        with tempfile.TemporaryDirectory() as root:
            first = LocalSettingsStore({"Username": "user one"}, root_path=root)
            second = LocalSettingsStore({"Username": "user two"}, root_path=root)

            first.save_general({"lab_name": "المخبر الأول"})
            second.save_general({"lab_name": "المخبر الثاني"})

            self.assertEqual(first.load_general()["lab_name"], "المخبر الأول")
            self.assertEqual(second.load_general()["lab_name"], "المخبر الثاني")
            self.assertNotEqual(first.general_path, second.general_path)

    def test_legacy_general_settings_are_copied_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as root:
            legacy_path = os.path.join(root, "legacy_config.json")
            legacy_payload = {"selected_printer": "Legacy", "gap": 3}
            with open(legacy_path, "w", encoding="utf-8") as handle:
                json.dump(legacy_payload, handle)

            store = LocalSettingsStore("operator", root_path=root)
            store.legacy_general_path = legacy_path

            self.assertEqual(store.load_general(), legacy_payload)
            self.assertTrue(os.path.exists(store.general_path))
            with open(legacy_path, "r", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), legacy_payload)

    def test_stamp_activation_and_deletion_keep_one_active_stamp(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalSettingsStore("operator", root_path=root)
            first = store.add_stamp("First", b"first", 1, 2, 3, 4)
            second = store.add_stamp("Second", b"second", 5, 6, 7, 8)

            self.assertEqual(store.get_active_stamp()["Stamp_ID"], first)
            self.assertTrue(store.set_active_stamp(second))
            self.assertEqual(store.get_active_stamp()["Stamp_ID"], second)

            self.assertTrue(store.delete_stamp(second))
            self.assertEqual(store.get_active_stamp()["Stamp_ID"], first)

    def test_pdf_banner_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            store = LocalSettingsStore("operator", root_path=root)
            store.save_pdf({"theme_color": "#123456"}, banner_bytes=b"png-data")

            self.assertEqual(store.load_pdf()["theme_color"], "#123456")
            self.assertEqual(store.load_banner_bytes(), b"png-data")


if __name__ == "__main__":
    unittest.main()
