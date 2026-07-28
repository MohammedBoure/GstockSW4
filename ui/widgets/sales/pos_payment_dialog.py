"""Dialog used by the POS to collect one or more tender lines."""

from decimal import Decimal, ROUND_HALF_UP

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


MONEY = Decimal("0.01")
PAYMENT_OPTIONS = (
    ("Espèces", "Cash"),
    ("Carte", "Card"),
    ("Virement", "Transfer"),
    ("Versement", "Versement"),
    ("Autre", "Other"),
    ("Crédit client", "Credit"),
)


def _money(value):
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


class PaymentDialog(QDialog):
    """Collect split payments while keeping the POS UI compact."""

    def __init__(self, total, parent=None, default_method="Cash", credit_summary=None):
        self.credit_summary = credit_summary or {}
        super().__init__(parent)
        self.total = _money(total)
        self.rows = []
        self.setWindowTitle("Paiement de la vente")
        self.setMinimumWidth(720)
        self._build_ui(default_method)
        self._add_row(default_method, self.total, self.total)
        self._update_totals()

    def _build_ui(self, default_method):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel(f"Total à payer : {self.total:.2f} DA")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #1f2937;")
        layout.addWidget(title)

        hint = QLabel("Vous pouvez répartir le montant sur plusieurs moyens de paiement.")
        hint.setStyleSheet("color: #64748b;")
        layout.addWidget(hint)

        if self.credit_summary:
            credit_label = QLabel(
                f"Credit client: {self.credit_summary.get('Credit_Balance', 0):.2f} DA utilisés | "
                f"Disponible: {self.credit_summary.get('Available_Credit') if self.credit_summary.get('Available_Credit') is not None else 'Illimité'} DA"
            )
            credit_label.setStyleSheet("color: #7c3aed; font-weight: 700;")
            layout.addWidget(credit_label)

        self.rows_widget = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_widget)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(6)
        layout.addWidget(self.rows_widget)

        self.btn_add = QPushButton("+ Ajouter un paiement")
        self.btn_add.clicked.connect(lambda: self._add_row("Card", Decimal("0"), Decimal("0")))
        layout.addWidget(self.btn_add, alignment=Qt.AlignLeft)

        self.lbl_totals = QLabel()
        self.lbl_totals.setStyleSheet("font-size: 14px; font-weight: 700; padding: 8px; background: #f8fafc; border-radius: 6px;")
        layout.addWidget(self.lbl_totals)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._accept_checked)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _add_row(self, default_method, amount, tendered):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        method = QComboBox()
        for label, value in PAYMENT_OPTIONS:
            method.addItem(label, value)
        index = method.findData(default_method)
        method.setCurrentIndex(index if index >= 0 else 0)
        method.setMinimumWidth(150)

        amount_spin = QDoubleSpinBox()
        amount_spin.setRange(0, float(self.total))
        amount_spin.setDecimals(2)
        amount_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        amount_spin.setPrefix("Montant ")
        amount_spin.setValue(float(amount))

        tendered_spin = QDoubleSpinBox()
        tendered_spin.setRange(0, float(self.total) * 2 + 100)
        tendered_spin.setDecimals(2)
        tendered_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        tendered_spin.setPrefix("Remis ")
        tendered_spin.setValue(float(tendered))

        reference = QLineEdit()
        reference.setPlaceholderText("Référence")
        reference.setMinimumWidth(130)

        remove = QPushButton("×")
        remove.setFixedWidth(32)
        remove.clicked.connect(lambda: self._remove_row(row_widget))

        row_layout.addWidget(method)
        row_layout.addWidget(amount_spin, 1)
        row_layout.addWidget(tendered_spin, 1)
        row_layout.addWidget(reference, 1)
        row_layout.addWidget(remove)
        self.rows_layout.addWidget(row_widget)
        row = {
            "widget": row_widget,
            "method": method,
            "amount": amount_spin,
            "tendered": tendered_spin,
            "reference": reference,
        }
        self.rows.append(row)
        amount_spin.valueChanged.connect(self._update_totals)
        tendered_spin.valueChanged.connect(self._update_totals)
        method.currentIndexChanged.connect(self._update_totals)

    def _remove_row(self, widget):
        if len(self.rows) <= 1:
            return
        for row in list(self.rows):
            if row["widget"] is widget:
                self.rows.remove(row)
                self.rows_layout.removeWidget(widget)
                widget.deleteLater()
                break
        self._update_totals()

    def _update_totals(self):
        applied = sum((_money(row["amount"].value()) for row in self.rows), Decimal("0"))
        remaining = self.total - applied
        self.lbl_totals.setText(
            f"Appliqué : {applied:.2f} DA    |    Reste : {remaining:.2f} DA"
        )
        self.lbl_totals.setStyleSheet(
            "font-size: 14px; font-weight: 700; padding: 8px; border-radius: 6px; "
            + ("background: #dcfce7; color: #166534;" if remaining == 0 else "background: #fef3c7; color: #92400e;")
        )

    def _accept_checked(self):
        lines = self.get_payment_lines()
        applied = sum((_money(line["amount"]) for line in lines), Decimal("0"))
        if applied != self.total:
            QMessageBox.warning(self, "Paiement incomplet", f"Le paiement doit totaliser {self.total:.2f} DA.")
            return
        for line in lines:
            if line["method"] == "Credit" and not line["reference"]:
                # The client/credit limit is checked by the data layer; a
                # reference remains optional, so do not block the cashier.
                continue
            if line["tendered"] < line["amount"]:
                QMessageBox.warning(self, "Montant remis invalide", "Le montant remis est inférieur au montant du paiement.")
                return
        self.accept()

    def get_payment_lines(self):
        return [
            {
                "method": row["method"].currentData(),
                "amount": _money(row["amount"].value()),
                "tendered": _money(row["tendered"].value()),
                "reference": row["reference"].text().strip() or None,
            }
            for row in self.rows
            if _money(row["amount"].value()) > 0
        ]
