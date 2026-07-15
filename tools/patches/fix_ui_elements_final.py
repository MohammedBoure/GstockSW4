import os

filepath = r"d:\git\GstockSW4\ui\widgets\settings\barcode_visual_editor.py"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Since the file is corrupted at the end and has multiple duplicates of update_ui_from_config
# Let's just find the first occurrence of "def update_ui_from_config(self):"
# and delete EVERYTHING after it, then append the pristine implementation.

idx = content.find("    def update_ui_from_config(self):")
if idx != -1:
    content = content[:idx]

new_func = """    def update_ui_from_config(self):
        self.sp_w.blockSignals(True); self.sp_w.setValue(self.label_config["label_width_mm"]); self.sp_w.blockSignals(False)
        self.sp_h.blockSignals(True); self.sp_h.setValue(self.label_config["label_height_mm"]); self.sp_h.blockSignals(False)
        
        for key in ["barcode", "product", "lot", "expiry", "company"]:
            el = self.label_config["elements"][key]
            chk = getattr(self, f"chk_{key}", None)
            if chk:
                chk.blockSignals(True); chk.setChecked(el["show"]); chk.blockSignals(False)
                
            sx = getattr(self, f"sp_{key}_x", None)
            if sx:
                sx.blockSignals(True); sx.setValue(el["x"]); sx.blockSignals(False)
                
            sy = getattr(self, f"sp_{key}_y", None)
            if sy:
                sy.blockSignals(True); sy.setValue(el["y"]); sy.blockSignals(False)
                
            sz = getattr(self, f"sp_{key}_sz", None)
            if sz:
                sz.blockSignals(True)
                sz.setValue(el.get("text_size" if key == "barcode" else "size", 10))
                sz.blockSignals(False)
                
            if key == "barcode":
                sw = getattr(self, "sp_barcode_w", None)
                if sw: sw.blockSignals(True); sw.setValue(el.get("width", 30)); sw.blockSignals(False)
                sh = getattr(self, "sp_barcode_h", None)
                if sh: sh.blockSignals(True); sh.setValue(el.get("height", 8)); sh.blockSignals(False)
            else:
                cmb_a = getattr(self, f"cmb_{key}_a", None)
                if cmb_a:
                    cmb_a.blockSignals(True)
                    cmb_a.setCurrentText(f"{el.get('angle', 0)}°")
                    cmb_a.blockSignals(False)
                    
            if key in ["lot", "expiry"]:
                inp_pref = getattr(self, f"inp_{key}_pref", None)
                if inp_pref:
                    inp_pref.blockSignals(True); inp_pref.setText(el.get("prefix", "")); inp_pref.blockSignals(False)
                    
            if key == "company":
                inp_txt = getattr(self, f"inp_{key}_txt", None)
                if inp_txt:
                    inp_txt.blockSignals(True); inp_txt.setText(el.get("text", "")); inp_txt.blockSignals(False)
"""

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content + new_func)

print("Fixed update_ui_from_config correctly.")
