import codecs

path = r'd:\git\Gstock\ui\widgets\inventory\tabs_batches\_table.py'
with codecs.open(path, 'r', 'utf-8') as f:
    content = f.read()

start_str = "    table.setItem(r, 7,  _make_item(b.get('Lot_Number', '---')))"
end_str = "def on_header_clicked(self, col_index):"

idx1 = content.find(start_str)
idx2 = content.find(end_str)

new_middle = """    table.setItem(r, 7,  _make_item(b.get('Lot_Number', '---')))
    table.setItem(r, 8,  _make_item(str(b.get('Expiry_Date', ''))[:10]))
    table.setItem(r, 9,  _make_item(format_quantity(b.get('Quantity_Initial', 0))))
    table.setItem(r, 10, _make_item(
        b.get('Internal_Barcode') or b.get('Barcode')
    ))

    # تطبيق الفلتر المالي على الصف
    if not hide_fin:
        p  = float(b.get('Unit_Price_Received', 0))
        d  = float(b.get('Discount_Percent', 0)) / 100.0
        t  = float(b.get('Tax_Rate_Percent', 0)) / 100.0
        lv = qty * p * (1 - d) * (1 + t)
        sv1 = float(b.get('Selling_Price_HT', 0))
        sv2 = float(b.get('Selling_Price_HT_2', 0))
        sv3 = float(b.get('Selling_Price_HT_3', 0))
        sv4 = float(b.get('Selling_Price_HT_4', 0))
        
        table.setItem(r, 11, _make_item(format_money(p)))
        table.setItem(r, 12, _make_item(format_money(lv)))
        table.setItem(r, 13, _make_item(format_money(sv1)))
        table.setItem(r, 14, _make_item(format_money(sv2)))
        table.setItem(r, 15, _make_item(format_money(sv3)))
        table.setItem(r, 16, _make_item(format_money(sv4)))
    else:
        table.setItem(r, 11, QTableWidgetItem(''))
        table.setItem(r, 12, QTableWidgetItem(''))
        table.setItem(r, 13, QTableWidgetItem(''))
        table.setItem(r, 14, QTableWidgetItem(''))
        table.setItem(r, 15, QTableWidgetItem(''))
        table.setItem(r, 16, QTableWidgetItem(''))

    table.setItem(r, 17, _make_item(b.get('PO_ID')))
    table.setItem(r, 18, _make_item(b.get('Location_Name')))

# ---------------------------------------------------------------------------
# الفرز
# ---------------------------------------------------------------------------

COL_MAP = {
    0: 'Product_Name',      1: 'Family_Name',
    2: 'Manuf_Name',        3: 'Automate_Name',
    4: 'Supplier_Name',     5: 'Quantity_Current',
    6: 'Date_Received',     7: 'Lot_Number',
    8: 'Expiry_Date',       9: 'Quantity_Initial',
    10: 'Internal_Barcode', 11: 'Unit_Price_Received',
    12: 'Total_Value',      13: 'Selling_Price_HT',
    14: 'Selling_Price_HT_2', 15: 'Selling_Price_HT_3',
    16: 'Selling_Price_HT_4', 17: 'PO_ID',
    18: 'Location_Name',
}

NUMERIC_COLS = {5, 9, 11, 13, 14, 15, 16}
DATE_COLS    = {6, 8}

def _sort_key(col_index, item):
    if col_index == 12:
        try:
            return (float(item.get('Quantity_Current', 0))
                    * float(item.get('Unit_Price_Received', 0)))
        except Exception:
            return 0.0

    key_name = COL_MAP.get(col_index)
    val = item.get(key_name)

    if val is None:
        return -1 if col_index in NUMERIC_COLS else ''

    if col_index in NUMERIC_COLS:
        try:
            return float(val)
        except Exception:
            return 0.0
    elif col_index in DATE_COLS:
        return str(val)[:10]
    else:
        return str(val).lower()

"""

new_content = content[:idx1] + new_middle + content[idx2:]

with codecs.open(path, 'w', 'utf-8') as f:
    f.write(new_content)
print('Done!')
