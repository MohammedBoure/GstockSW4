import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.widgets.history import MovementHistoryTab


class FakeMovementManager:
    def __init__(self):
        self.count_calls = []
        self.log_calls = []

    def get_movements_count(self, **filters):
        self.count_calls.append(filters)
        return 51

    def get_movements_log(self, *, limit, offset, **filters):
        self.log_calls.append({"limit": limit, "offset": offset, **filters})
        if offset == 0:
            return [self._movement(index) for index in range(50)]
        if offset == 50:
            return [self._movement(50)]
        return []

    @staticmethod
    def _movement(index):
        return {
            "Movement_ID": index + 1,
            "Transaction_Date": "2026-07-28 10:00:00",
            "Product_Name": "Product %s" % index,
            "Batch_Barcode": "BC-%s" % index,
            "Lot_Number": "LOT-%s" % index,
            "Movement_Type": "Sale" if index == 50 else "Purchase_Receive",
            "Qty_Change": 1,
            "Batch_Historical_Stock": 10,
            "Location_Name": "Main",
            "Operator_Name": "BENZAID",
            "Reason_Name": "",
            "Notes": "",
        }


class FakeDataManager:
    def __init__(self):
        self.movement = FakeMovementManager()


class MovementHistoryWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_incremental_loading_and_target_movement_types(self):
        manager = FakeDataManager()
        widget = MovementHistoryTab(manager)
        self.app.processEvents()

        self.assertEqual(widget.table.rowCount(), 50)
        self.assertEqual(widget.lbl_status.text(), "50/51")
        self.assertTrue(widget.has_more_data)
        self.assertTrue(widget.date_from.isEnabled())
        self.assertTrue(widget.date_to.isEnabled())
        self.assertGreaterEqual(widget.combo_type.findData("Sale"), 0)
        self.assertGreaterEqual(widget.combo_type.findData("Sale_Return"), 0)

        widget.load_next_batch()

        self.assertEqual(widget.table.rowCount(), 51)
        self.assertEqual(widget.lbl_status.text(), "51/51")
        self.assertFalse(widget.has_more_data)
        self.assertEqual(len(manager.movement.count_calls), 1)
        self.assertEqual([call["offset"] for call in manager.movement.log_calls], [0, 50])
        self.assertEqual([call["limit"] for call in manager.movement.log_calls], [50, 50])

        widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
