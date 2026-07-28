"""Compatibility exports for the former monolithic reception dialog module.

GstockSW4 now keeps the reception dialog in the canonical package below, but
older plugins and local scripts may still import ui.widgets.procurement._.
"""

from .bulk_barcode_selection_dialog import BulkBarcodeSelectionDialog
from .location_tree_combo import LocationTreeComboBox
from .reception_dialog import (
    AutoSelectDoubleSpinBox,
    AutoSelectLineEdit,
    AutoSelectSpinBox,
    ReceptionDialog,
)

__all__ = [
    "AutoSelectSpinBox",
    "AutoSelectLineEdit",
    "AutoSelectDoubleSpinBox",
    "ReceptionDialog",
    "LocationTreeComboBox",
    "BulkBarcodeSelectionDialog",
]
