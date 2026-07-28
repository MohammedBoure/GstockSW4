"""Pure helpers for backward-compatible receipt template settings."""

from copy import deepcopy


def merge_receipt_config(defaults, saved):
    """Merge a saved/legacy receipt config without losing schema defaults.

    Older rows in Print_Templates may contain only a subset of the current
    receipt settings. Nested default dictionaries are kept when a legacy row
    omits them or contains an invalid non-dictionary value. Inputs are never
    mutated, and unknown keys are retained for forward compatibility.
    """
    result = deepcopy(defaults) if isinstance(defaults, dict) else {}
    if not isinstance(saved, dict):
        return result

    for key, value in saved.items():
        current = result.get(key)
        if isinstance(current, dict):
            if isinstance(value, dict):
                result[key] = merge_receipt_config(current, value)
            continue
        result[key] = deepcopy(value)

    return result
