import unittest

from ui.navigation_permissions import has_navigation_permission, has_permission


class NavigationPermissionTests(unittest.TestCase):
    def test_sales_navigation_falls_back_to_existing_sales_permissions(self):
        user = {"Permissions": {"tab_sales_invoices": True}}

        self.assertTrue(has_navigation_permission(user, "nav_sales"))

    def test_explicit_navigation_deny_is_not_overridden(self):
        user = {
            "Permissions": {
                "nav_sales": False,
                "tab_sales_invoices": True,
            }
        }

        self.assertFalse(has_navigation_permission(user, "nav_sales"))

    def test_missing_navigation_and_feature_permissions_stays_hidden(self):
        self.assertFalse(has_navigation_permission({"Permissions": {}}, "nav_sales"))

    def test_json_permissions_and_explicit_feature_checks_are_supported(self):
        user = {"Permissions": '{"nav_sales": true, "act_create_sale": false}'}

        self.assertTrue(has_permission(user, "nav_sales"))
        self.assertFalse(has_permission(user, "act_create_sale"))


if __name__ == "__main__":
    unittest.main()
