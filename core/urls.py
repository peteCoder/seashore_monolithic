from django.urls import path

from core.views import (
    register_view,
    login_view,
    password_reset_confirm_view,
    password_reset_request_view,
    logout_view,
    dashboard_view,
)

from core.views.client_views import (
    client_list,
    client_detail,
    client_create,
    client_update,
    client_approve,
    client_activate,
    client_deactivate,
    client_delete,
    client_assign_staff,
    client_pay_registration_fee,
)

from core.views.branch_views import (
    branch_list,
    branch_detail,
    branch_create,
    branch_update,
    branch_activate,
    branch_deactivate,
    branch_delete,
)

from core.views.savings_product_views import (
    savings_product_list,
    savings_product_detail,
    savings_product_create,
    savings_product_update,
    savings_product_activate,
    savings_product_deactivate,
    savings_product_delete,
)

from core.views.savings_views import (
    savings_account_list,
    savings_account_detail,
    savings_account_create,
    savings_account_approve,
    savings_deposit_post,
    savings_deposit_post_bulk,
    savings_withdrawal_post,
    savings_withdrawal_post_bulk,
    savings_transaction_list,
    savings_transaction_approve,
    savings_transaction_approve_bulk,
)

from core.views.loan_product_views import (
    loan_product_list,
    loan_product_detail,
    loan_product_create,
    loan_product_update,
    loan_product_activate,
    loan_product_deactivate,
    loan_product_delete,
)

from core.views.group_views import (
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

from core.views.group_collection_views import (
    group_collection_list,
    group_collection_detail,
    group_collection_post,
    group_collection_session_detail,
    group_collection_approve,
    group_savings_collection,
    group_savings_collection_post,
    group_savings_session_detail,
    group_savings_collection_approve,
)

from core.views.user_views import (
    user_list,
    user_create,
    user_detail,
    user_edit,
    user_delete,
    user_assign_branch,
    user_profile,
    user_profile_edit,
)

from core.views.transaction_views import (
    transaction_detail,
)

from core.views.accounting_views import (
    # Dashboard
    accounting_dashboard,
    # Chart of Accounts
    chart_of_accounts_list,
    chart_of_accounts_detail,
    chart_of_accounts_create,
    chart_of_accounts_edit,
    # Journal Entries
    journal_entry_list,
    journal_entry_detail,
    journal_entry_create,
    journal_entry_post,
    journal_entry_reverse,
    # Financial Reports
    report_trial_balance,
    report_profit_loss,
    report_balance_sheet,
    report_general_ledger,
    report_cash_flow,
    report_transaction_audit,
)

from core.views.loan_views import (
    loan_list,
    loan_detail,
    loan_create,
    loan_pay_fees,
    loan_approve,
    loan_disburse,
    loan_repayment_post,
    loan_repayment_post_bulk,
    loan_repayment_list,
    loan_repayment_approve,
    loan_repayment_approve_bulk,
    loan_product_api,
    loan_guarantors,
    loan_add_guarantor,
    loan_edit_guarantor,
    loan_delete_guarantor,
)


app_name = "core"

urlpatterns = [
    # =========================================================================
    # AUTHENTICATION
    # =========================================================================
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('password-reset/', password_reset_request_view, name='password_reset_request'),
    path('reset-password/<str:token>/', password_reset_confirm_view, name='password_reset_confirm'),

    # =========================================================================
    # DASHBOARD
    # =========================================================================
    path('', dashboard_view, name='dashboard'),
    path('dashboard/', dashboard_view, name='dashboard_alt'),

    # =========================================================================
    # CLIENTS
    # =========================================================================
    path('clients/', client_list, name='client_list'),
    path('clients/create/', client_create, name='client_create'),
    path('clients/<uuid:client_id>/', client_detail, name='client_detail'),
    path('clients/<uuid:client_id>/edit/', client_update, name='client_update'),
    path('clients/<uuid:client_id>/approve/', client_approve, name='client_approve'),
    path('clients/<uuid:client_id>/activate/', client_activate, name='client_activate'),
    path('clients/<uuid:client_id>/deactivate/', client_deactivate, name='client_deactivate'),
    path('clients/<uuid:client_id>/delete/', client_delete, name='client_delete'),
    path('clients/<uuid:client_id>/assign-staff/', client_assign_staff, name='client_assign_staff'),
    path('clients/<uuid:client_id>/pay-registration-fee/', client_pay_registration_fee, name='client_pay_registration_fee'),

    # =========================================================================
    # BRANCHES
    # =========================================================================
    path('branches/', branch_list, name='branch_list'),
    path('branches/create/', branch_create, name='branch_create'),
    path('branches/<uuid:branch_id>/', branch_detail, name='branch_detail'),
    path('branches/<uuid:branch_id>/edit/', branch_update, name='branch_update'),
    path('branches/<uuid:branch_id>/activate/', branch_activate, name='branch_activate'),
    path('branches/<uuid:branch_id>/deactivate/', branch_deactivate, name='branch_deactivate'),
    path('branches/<uuid:branch_id>/delete/', branch_delete, name='branch_delete'),

    # =========================================================================
    # SAVINGS PRODUCTS
    # =========================================================================
    path('products/savings/', savings_product_list, name='savings_product_list'),
    path('products/savings/create/', savings_product_create, name='savings_product_create'),
    path('products/savings/<uuid:product_id>/', savings_product_detail, name='savings_product_detail'),
    path('products/savings/<uuid:product_id>/edit/', savings_product_update, name='savings_product_update'),
    path('products/savings/<uuid:product_id>/activate/', savings_product_activate, name='savings_product_activate'),
    path('products/savings/<uuid:product_id>/deactivate/', savings_product_deactivate, name='savings_product_deactivate'),
    path('products/savings/<uuid:product_id>/delete/', savings_product_delete, name='savings_product_delete'),

    # =========================================================================
    # SAVINGS ACCOUNTS
    # =========================================================================
    path('savings/', savings_account_list, name='savings_account_list'),
    path('savings/create/', savings_account_create, name='savings_account_create'),
    path('savings/<uuid:account_id>/', savings_account_detail, name='savings_account_detail'),
    path('savings/<uuid:account_id>/approve/', savings_account_approve, name='savings_account_approve'),

    # Savings Deposits
    path('savings/deposits/post/', savings_deposit_post, name='savings_deposit_post'),
    path('savings/deposits/post/<uuid:account_id>/', savings_deposit_post, name='savings_deposit_post_for_account'),
    path('savings/deposits/post/bulk/', savings_deposit_post_bulk, name='savings_deposit_post_bulk'),
    path('savings/deposits/<uuid:posting_id>/approve/', savings_transaction_approve, {'posting_type': 'deposit'}, name='savings_deposit_approve'),

    # Savings Withdrawals
    path('savings/withdrawals/post/', savings_withdrawal_post, name='savings_withdrawal_post'),
    path('savings/withdrawals/post/<uuid:account_id>/', savings_withdrawal_post, name='savings_withdrawal_post_for_account'),
    path('savings/withdrawals/post/bulk/', savings_withdrawal_post_bulk, name='savings_withdrawal_post_bulk'),
    path('savings/withdrawals/<uuid:posting_id>/approve/', savings_transaction_approve, {'posting_type': 'withdrawal'}, name='savings_withdrawal_approve'),

    # Combined Transaction Views
    path('savings/transactions/', savings_transaction_list, name='savings_transaction_list'),
    path('savings/transactions/approve/bulk/', savings_transaction_approve_bulk, name='savings_transaction_approve_bulk'),

    # =========================================================================
    # LOAN PRODUCTS
    # =========================================================================
    path('products/loans/', loan_product_list, name='loan_product_list'),
    path('products/loans/create/', loan_product_create, name='loan_product_create'),
    path('products/loans/<uuid:product_id>/', loan_product_detail, name='loan_product_detail'),
    path('products/loans/<uuid:product_id>/edit/', loan_product_update, name='loan_product_update'),
    path('products/loans/<uuid:product_id>/activate/', loan_product_activate, name='loan_product_activate'),
    path('products/loans/<uuid:product_id>/deactivate/', loan_product_deactivate, name='loan_product_deactivate'),
    path('products/loans/<uuid:product_id>/delete/', loan_product_delete, name='loan_product_delete'),

    # =========================================================================
    # CLIENT GROUPS
    # =========================================================================
    path('groups/', group_list, name='group_list'),
    path('groups/create/', group_create, name='group_create'),
    path('groups/<uuid:group_id>/', group_detail, name='group_detail'),
    path('groups/<uuid:group_id>/edit/', group_update, name='group_update'),
    path('groups/<uuid:group_id>/approve/', group_approve, name='group_approve'),

    # Member Management
    path('groups/<uuid:group_id>/add-member/', group_add_member, name='group_add_member'),
    path('groups/<uuid:group_id>/add-members-bulk/', group_add_members_bulk, name='group_add_members_bulk'),
    path('groups/<uuid:group_id>/approve-members-bulk/', group_approve_members_bulk, name='group_approve_members_bulk'),
    path('groups/<uuid:group_id>/members/<uuid:client_id>/remove/', group_remove_member, name='group_remove_member'),
    path('groups/<uuid:group_id>/members/<uuid:client_id>/update-role/', group_update_member_role, name='group_update_member_role'),
    path('groups/membership-requests/<uuid:request_id>/approve/', group_approve_member, name='group_approve_member'),

    # Group Collections - Loan Repayments
    path('groups/collections/', group_collection_list, name='group_collection_list'),
    path('groups/<uuid:group_id>/collect/', group_collection_detail, name='group_collection_detail'),
    path('groups/<uuid:group_id>/collect/post/', group_collection_post, name='group_collection_post'),
    path('groups/collections/<uuid:session_id>/', group_collection_session_detail, name='group_collection_session_detail'),
    path('groups/collections/<uuid:session_id>/approve/', group_collection_approve, name='group_collection_approve'),

    # Group Collections - Savings
    path('groups/<uuid:group_id>/collect-savings/', group_savings_collection, name='group_savings_collection'),
    path('groups/<uuid:group_id>/collect-savings/post/', group_savings_collection_post, name='group_savings_collection_post'),
    path('groups/savings-collections/<uuid:session_id>/', group_savings_session_detail, name='group_savings_session_detail'),
    path('groups/savings-collections/<uuid:session_id>/approve/', group_savings_collection_approve, name='group_savings_collection_approve'),

    # =========================================================================
    # USERS/STAFF MANAGEMENT
    # =========================================================================
    path('staff/', user_list, name='user_list'),
    path('staff/create/', user_create, name='user_create'),
    path('staff/<uuid:user_id>/', user_detail, name='user_detail'),
    path('staff/<uuid:user_id>/edit/', user_edit, name='user_edit'),
    path('staff/<uuid:user_id>/delete/', user_delete, name='user_delete'),
    path('staff/<uuid:user_id>/assign-branch/', user_assign_branch, name='user_assign_branch'),

    # User Profile (for logged-in user)
    path('profile/', user_profile, name='user_profile'),
    path('profile/edit/', user_profile_edit, name='user_profile_edit'),

    # =========================================================================
    # TRANSACTIONS
    # =========================================================================
    path('transactions/<uuid:transaction_id>/', transaction_detail, name='transaction_detail'),

    # =========================================================================
    # LOANS
    # =========================================================================
    path('loans/', loan_list, name='loan_list'),
    path('loans/create/', loan_create, name='loan_create'),
    path('loans/<uuid:loan_id>/', loan_detail, name='loan_detail'),
    path('loans/<uuid:loan_id>/pay-fees/', loan_pay_fees, name='loan_pay_fees'),
    path('loans/<uuid:loan_id>/approve/', loan_approve, name='loan_approve'),
    path('loans/<uuid:loan_id>/disburse/', loan_disburse, name='loan_disburse'),

    # Loan Guarantors
    path('loans/<uuid:loan_id>/guarantors/', loan_guarantors, name='loan_guarantors'),
    path('loans/<uuid:loan_id>/guarantors/add/', loan_add_guarantor, name='loan_add_guarantor'),
    path('loans/<uuid:loan_id>/guarantors/<uuid:guarantor_id>/edit/', loan_edit_guarantor, name='loan_edit_guarantor'),
    path('loans/<uuid:loan_id>/guarantors/<uuid:guarantor_id>/delete/', loan_delete_guarantor, name='loan_delete_guarantor'),

    # Loan Repayments
    path('loans/repayments/', loan_repayment_list, name='loan_repayment_list'),
    path('loans/repayments/post/', loan_repayment_post, name='loan_repayment_post'),
    path('loans/repayments/post/<uuid:loan_id>/', loan_repayment_post, name='loan_repayment_post_for_loan'),
    path('loans/repayments/post/bulk/', loan_repayment_post_bulk, name='loan_repayment_post_bulk'),
    path('loans/repayments/<uuid:posting_id>/approve/', loan_repayment_approve, name='loan_repayment_approve'),
    path('loans/repayments/approve/bulk/', loan_repayment_approve_bulk, name='loan_repayment_approve_bulk'),

    # Loan Product API
    path('api/loan-product/<uuid:product_id>/', loan_product_api, name='loan_product_api'),

    # =========================================================================
    # ACCOUNTING MODULE
    # =========================================================================

    # Dashboard
    path('accounting/', accounting_dashboard, name='accounting_dashboard'),

    # Chart of Accounts
    path('accounting/coa/', chart_of_accounts_list, name='coa_list'),
    path('accounting/coa/create/', chart_of_accounts_create, name='coa_create'),
    path('accounting/coa/<uuid:account_id>/', chart_of_accounts_detail, name='coa_detail'),
    path('accounting/coa/<uuid:account_id>/edit/', chart_of_accounts_edit, name='coa_edit'),

    # Journal Entries
    path('accounting/journals/', journal_entry_list, name='journal_entry_list'),
    path('accounting/journals/create/', journal_entry_create, name='journal_entry_create'),
    path('accounting/journals/<uuid:entry_id>/', journal_entry_detail, name='journal_entry_detail'),
    path('accounting/journals/<uuid:entry_id>/post/', journal_entry_post, name='journal_entry_post'),
    path('accounting/journals/<uuid:entry_id>/reverse/', journal_entry_reverse, name='journal_entry_reverse'),

    # Financial Reports
    path('accounting/reports/trial-balance/', report_trial_balance, name='report_trial_balance'),
    path('accounting/reports/profit-loss/', report_profit_loss, name='report_profit_loss'),
    path('accounting/reports/balance-sheet/', report_balance_sheet, name='report_balance_sheet'),
    path('accounting/reports/general-ledger/', report_general_ledger, name='report_general_ledger'),
    path('accounting/reports/cash-flow/', report_cash_flow, name='report_cash_flow'),
    path('accounting/reports/transaction-audit/', report_transaction_audit, name='report_transaction_audit'),

]
  





