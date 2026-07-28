"""Backward-compatible navigation permission checks.

The target application historically stored detailed feature permissions without
always storing the corresponding navigation permission. These helpers preserve
access to an existing feature while still respecting an explicit navigation
deny.
"""

import json


NAVIGATION_PERMISSION_FALLBACKS = {
    "nav_dashboard": (
        "tab_dash_overview",
        "tab_dash_reception",
        "tab_dash_consumption",
        "tab_dash_valuation",
        "tab_dash_waste",
        "tab_dash_alerts",
    ),
    "nav_data": (
        "tab_data_products",
        "tab_data_families",
        "tab_data_units",
        "tab_data_suppliers",
        "tab_data_manufacturers",
        "tab_data_partners",
        "tab_data_automates",
        "tab_data_locations",
        "tab_data_waste_reasons",
        "tab_clients",
    ),
    "nav_procurement": (
        "tab_proc_po",
        "tab_proc_reception",
        "tab_proc_credit",
        "tab_proc_reclamation",
    ),
    "nav_inventory": ("tab_inv_list", "tab_inv_dispatch"),
    "nav_inventaire": (
        "act_inventory_create",
        "act_inventory_scan",
        "act_inventory_apply",
        "act_inventory_cancel",
        "act_inventory_export",
    ),
    "nav_services": ("nav_market",),
    "nav_history": ("tab_inv_history",),
    "nav_sales": (
        "tab_sales_invoices",
        "tab_sales_returns",
        "tab_sales_payments",
        "act_create_sale",
        "act_validate_sale",
        "act_sale_without_client",
        "act_return_sale",
        "act_cancel_sale",
        "act_edit_sale",
        "act_pos_open_session",
        "act_pos_close_session",
        "act_edit_closed_cash_session",
    ),
    "nav_settings": (
        "tab_config",
        "tab_set_db",
        "tab_set_printer",
        "tab_set_system",
        "tab_system_logs",
        "tab_set_pdf",
    ),
}


def _permissions(user):
    if not isinstance(user, dict):
        return {}

    permissions = user.get("Permissions", {})
    if isinstance(permissions, str):
        try:
            permissions = json.loads(permissions)
        except (TypeError, json.JSONDecodeError):
            return {}
    return permissions


def _permission_state(user, permission):
    permissions = _permissions(user)
    if isinstance(permissions, dict):
        if permission not in permissions:
            return False, False
        value = permissions.get(permission)
        if isinstance(value, str):
            value = value.strip().lower() not in {"", "0", "false", "no", "none", "null"}
        return True, bool(value)

    if isinstance(permissions, list):
        return permission in permissions, permission in permissions

    return False, False


def has_permission(user, permission):
    """Return the explicit value of one permission key."""
    return _permission_state(user, permission)[1]


def has_navigation_permission(user, permission):
    """Return navigation access without overriding an explicit deny."""
    present, granted = _permission_state(user, permission)
    if present:
        return granted

    return any(
        has_permission(user, fallback)
        for fallback in NAVIGATION_PERMISSION_FALLBACKS.get(permission, ())
    )
