"""Compatibility import for the canonical PDF settings widget."""

from .pdf.pdf_config_tab import PdfConfigWidget

PdfConfigTab = PdfConfigWidget

__all__ = ["PdfConfigWidget", "PdfConfigTab"]
