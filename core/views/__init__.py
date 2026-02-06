from .auth_views import (
    register_view,
    login_view,
    password_reset_confirm_view,
    password_reset_request_view,
    logout_view,
)

from .dashboard import (
    dashboard_view,
)

from .savings_product_views import (
    savings_product_list,
    savings_product_detail,
    savings_product_create,
    savings_product_update,
    savings_product_activate,
    savings_product_deactivate,
    savings_product_delete,
)

from .loan_product_views import (
    loan_product_list,
    loan_product_detail,
    loan_product_create,
    loan_product_update,
    loan_product_activate,
    loan_product_deactivate,
    loan_product_delete,
)

from .group_views import (
    group_list,
    group_detail,
    group_create,
    group_update,
    group_approve,
    group_add_member,
    group_add_members_bulk,
    group_approve_member,
    group_approve_members_bulk,
    group_remove_member,
    group_update_member_role,
)


__all__ = [
    "register_view",
    "login_view",
    "password_reset_confirm_view",
    "password_reset_request_view",
    "logout_view",
    "dashboard_view",
    # Savings Product Views
    "savings_product_list",
    "savings_product_detail",
    "savings_product_create",
    "savings_product_update",
    "savings_product_activate",
    "savings_product_deactivate",
    "savings_product_delete",
    # Loan Product Views
    "loan_product_list",
    "loan_product_detail",
    "loan_product_create",
    "loan_product_update",
    "loan_product_activate",
    "loan_product_deactivate",
    "loan_product_delete",
    # Group Views
    "group_list",
    "group_detail",
    "group_create",
    "group_update",
    "group_approve",
    "group_add_member",
    "group_add_members_bulk",
    "group_approve_member",
    "group_approve_members_bulk",
    "group_remove_member",
    "group_update_member_role",
]






























