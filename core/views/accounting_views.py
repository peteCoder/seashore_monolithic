"""
Accounting Views
================

Views for accounting module including:
- Chart of Accounts management
- Journal Entry management
- Financial Reports (Trial Balance, P&L, Balance Sheet, etc.)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F, Case, When, DecimalField, Value
from django.db.models.functions import TruncDate
from django.db import transaction as db_transaction
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta, datetime

from core.models import (
    ChartOfAccounts, JournalEntry, JournalEntryLine,
    Transaction, Branch, AccountType, AccountCategory
)
from core.forms.accounting_forms import (
    DateRangeForm, TrialBalanceForm, ProfitLossForm, BalanceSheetForm,
    GeneralLedgerForm, JournalEntrySearchForm,
    JournalEntryForm, JournalEntryLineFormSet, JournalReversalForm
)
from core.permissions import PermissionChecker
from core.utils.accounting_helpers import create_journal_entry
from core.utils.pdf_export import (
    generate_trial_balance_pdf, generate_profit_loss_pdf,
    generate_balance_sheet_pdf, generate_general_ledger_pdf,
    generate_cash_flow_pdf, generate_transaction_audit_pdf
)
from core.utils.excel_export import (
    export_trial_balance_excel, export_profit_loss_excel,
    export_balance_sheet_excel, export_general_ledger_excel,
    export_cash_flow_excel, export_transaction_audit_excel
)

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# ACCOUNTING DASHBOARD
# =============================================================================

@login_required
def accounting_dashboard(request):
    """
    Accounting Module Dashboard

    Displays key metrics, recent activity, and quick links
    Permissions: Manager, Director, Admin
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_director() or checker.is_admin()):
        messages.error(request, 'You do not have permission to access the accounting module.')
        raise PermissionDenied

    # Get cash account balance
    cash_account = ChartOfAccounts.objects.filter(gl_code='1010').first()
    cash_balance = Decimal('0.00')
    if cash_account:
        cash_debits = JournalEntryLine.objects.filter(
            account=cash_account,
            journal_entry__status='posted'
        ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')

        cash_credits = JournalEntryLine.objects.filter(
            account=cash_account,
            journal_entry__status='posted'
        ).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')

        cash_balance = cash_debits - cash_credits

    # Journal entry stats
    total_journals = JournalEntry.objects.count()
    unposted_journals = JournalEntry.objects.filter(status__in=['draft', 'pending']).count()

    # Get entries posted today (using date range)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    posted_today = JournalEntry.objects.filter(
        status='posted',
        posting_date__gte=today_start,
        posting_date__lte=today_end
    ).count()

    # Recent journal entries
    recent_journals = JournalEntry.objects.select_related('branch', 'created_by').order_by('-created_at')[:10]

    # Account summary by type
    account_types = AccountType.objects.all()
    accounts_by_type = []
    for acc_type in account_types:
        count = ChartOfAccounts.objects.filter(account_type=acc_type, is_active=True).count()
        accounts_by_type.append({
            'type': acc_type.get_name_display(),
            'count': count
        })

    # Transactions needing journal entries (audit check)
    transactions_without_journals = Transaction.objects.filter(
        status='completed'
    ).exclude(
        id__in=JournalEntry.objects.filter(transaction__isnull=False).values_list('transaction_id', flat=True)
    ).count()

    context = {
        'page_title': 'Accounting Dashboard',
        'cash_balance': cash_balance,
        'total_journals': total_journals,
        'unposted_journals': unposted_journals,
        'posted_today': posted_today,
        'recent_journals': recent_journals,
        'accounts_by_type': accounts_by_type,
        'transactions_without_journals': transactions_without_journals,
    }

    return render(request, 'accounting/accounting_dashboard.html', context)


# =============================================================================
# CHART OF ACCOUNTS VIEWS
# =============================================================================

@login_required
def chart_of_accounts_list(request):
    """
    Display hierarchical list of all GL accounts

    Permissions: Manager, Director, Admin
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_director() or checker.is_admin()):
        messages.error(request, 'You do not have permission to view Chart of Accounts.')
        raise PermissionDenied

    # Base queryset
    accounts = ChartOfAccounts.objects.select_related(
        'account_type', 'account_category', 'parent_account', 'branch'
    ).prefetch_related('journal_lines')

    # Filters
    account_type_filter = request.GET.get('account_type')
    if account_type_filter:
        accounts = accounts.filter(account_type__name=account_type_filter)

    is_active = request.GET.get('is_active')
    if is_active == 'true':
        accounts = accounts.filter(is_active=True)
    elif is_active == 'false':
        accounts = accounts.filter(is_active=False)

    branch_filter = request.GET.get('branch')
    if branch_filter:
        accounts = accounts.filter(Q(branch_id=branch_filter) | Q(branch__isnull=True))

    # Calculate balances for each account
    accounts_with_balances = []
    for account in accounts.order_by('gl_code'):
        # Calculate balance from journal lines
        debit_total = account.journal_lines.aggregate(
            total=Sum('debit_amount'))['total'] or Decimal('0')
        credit_total = account.journal_lines.aggregate(
            total=Sum('credit_amount'))['total'] or Decimal('0')

        # Balance depends on account type normal balance
        if account.account_type.normal_balance == 'debit':
            balance = debit_total - credit_total
        else:
            balance = credit_total - debit_total

        accounts_with_balances.append({
            'account': account,
            'debit_total': debit_total,
            'credit_total': credit_total,
            'balance': balance
        })

    # Pagination
    paginator = Paginator(accounts_with_balances, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': 'Chart of Accounts',
        'accounts': page_obj,
        'account_types': AccountType.TYPE_CHOICES,
        'branches': Branch.objects.filter(is_active=True),
        'total_accounts': accounts.count(),
    }

    return render(request, 'accounting/coa_list.html', context)


@login_required
def chart_of_accounts_detail(request, account_id):
    """
    Display account detail with transaction history

    Permissions: Manager, Director, Admin
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_director() or checker.is_admin()):
        messages.error(request, 'You do not have permission to view account details.')
        raise PermissionDenied

    account = get_object_or_404(
        ChartOfAccounts.objects.select_related('account_type', 'account_category', 'parent_account', 'branch'),
        id=account_id
    )

    # Get recent journal lines
    journal_lines = account.journal_lines.select_related(
        'journal_entry', 'journal_entry__branch', 'journal_entry__created_by', 'client'
    ).order_by('-journal_entry__transaction_date', '-journal_entry__created_at')[:100]

    # Calculate balances
    debit_total = account.journal_lines.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
    credit_total = account.journal_lines.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')

    if account.account_type.normal_balance == 'debit':
        balance = debit_total - credit_total
    else:
        balance = credit_total - debit_total

    # Get sub-accounts
    sub_accounts = ChartOfAccounts.objects.filter(parent_account=account)

    context = {
        'page_title': f'Account: {account.account_name}',
        'account': account,
        'debit_total': debit_total,
        'credit_total': credit_total,
        'balance': balance,
        'journal_lines': journal_lines,
        'sub_accounts': sub_accounts,
    }

    return render(request, 'accounting/coa_detail.html', context)


@login_required
def chart_of_accounts_create(request):
    """
    Create new GL account

    Permissions: Director, Admin only
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_director() or checker.is_admin()):
        messages.error(request, 'Only Directors and Administrators can create GL accounts.')
        raise PermissionDenied

    if request.method == 'POST':
        # Manual form processing since we're not using ModelForm
        gl_code = request.POST.get('gl_code')
        account_name = request.POST.get('account_name')
        account_type_id = request.POST.get('account_type')
        account_category_id = request.POST.get('account_category')
        parent_account_id = request.POST.get('parent_account')
        branch_id = request.POST.get('branch')
        description = request.POST.get('description', '')
        is_control_account = request.POST.get('is_control_account') == 'on'
        allows_manual_entries = request.POST.get('allows_manual_entries') == 'on'

        try:
            # Validate unique GL code
            if ChartOfAccounts.objects.filter(gl_code=gl_code).exists():
                messages.error(request, f'Account with GL Code {gl_code} already exists.')
            else:
                account = ChartOfAccounts.objects.create(
                    gl_code=gl_code,
                    account_name=account_name,
                    account_type_id=account_type_id,
                    account_category_id=account_category_id if account_category_id else None,
                    parent_account_id=parent_account_id if parent_account_id else None,
                    branch_id=branch_id if branch_id else None,
                    description=description,
                    is_control_account=is_control_account,
                    allows_manual_entries=allows_manual_entries,
                    currency='NGN',
                    is_active=True
                )

                messages.success(request, f'GL Account {account.gl_code} - {account.account_name} created successfully!')
                return redirect('core:coa_detail', account_id=account.id)
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')

    context = {
        'page_title': 'Create GL Account',
        'account_types': AccountType.objects.all(),
        'account_categories': AccountCategory.objects.select_related('account_type'),
        'parent_accounts': ChartOfAccounts.objects.filter(is_control_account=True, is_active=True),
        'branches': Branch.objects.filter(is_active=True),
    }

    return render(request, 'accounting/coa_form.html', context)


@login_required
def chart_of_accounts_edit(request, account_id):
    """
    Edit existing GL account

    Permissions: Director, Admin only
    Note: GL Code cannot be changed if transactions exist
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_director() or checker.is_admin()):
        messages.error(request, 'Only Directors and Administrators can edit GL accounts.')
        raise PermissionDenied

    account = get_object_or_404(ChartOfAccounts, id=account_id)

    # Check if account has transactions
    has_transactions = account.journal_lines.exists()

    if request.method == 'POST':
        account_name = request.POST.get('account_name')
        description = request.POST.get('description', '')
        is_control_account = request.POST.get('is_control_account') == 'on'
        allows_manual_entries = request.POST.get('allows_manual_entries') == 'on'

        try:
            account.account_name = account_name
            account.description = description
            account.is_control_account = is_control_account
            account.allows_manual_entries = allows_manual_entries

            # Only allow changing structural fields if no transactions
            if not has_transactions:
                gl_code = request.POST.get('gl_code')
                account_type_id = request.POST.get('account_type')
                account_category_id = request.POST.get('account_category')
                parent_account_id = request.POST.get('parent_account')
                branch_id = request.POST.get('branch')

                account.gl_code = gl_code
                account.account_type_id = account_type_id
                account.account_category_id = account_category_id if account_category_id else None
                account.parent_account_id = parent_account_id if parent_account_id else None
                account.branch_id = branch_id if branch_id else None

            account.save()

            messages.success(request, f'GL Account {account.gl_code} updated successfully!')
            return redirect('core:coa_detail', account_id=account.id)
        except Exception as e:
            messages.error(request, f'Error updating account: {str(e)}')

    context = {
        'page_title': f'Edit GL Account: {account.gl_code}',
        'account': account,
        'has_transactions': has_transactions,
        'account_types': AccountType.objects.all(),
        'account_categories': AccountCategory.objects.select_related('account_type'),
        'parent_accounts': ChartOfAccounts.objects.filter(is_control_account=True, is_active=True).exclude(id=account.id),
        'branches': Branch.objects.filter(is_active=True),
    }

    return render(request, 'accounting/coa_form.html', context)


# =============================================================================
# JOURNAL ENTRY VIEWS
# =============================================================================

@login_required
def journal_entry_list(request):
    """
    Display list of all journal entries with filters

    Permissions: Staff (own), Manager (branch), Director/Admin (all)
    """
    checker = PermissionChecker(request.user)

    # Base queryset
    journals = JournalEntry.objects.select_related(
        'branch', 'created_by', 'posted_by', 'transaction', 'loan', 'savings_account'
    ).prefetch_related('lines')

    # Permission-based filtering
    if checker.is_staff():
        journals = journals.filter(created_by=request.user)
    elif checker.is_manager():
        journals = journals.filter(branch=request.user.branch)

    # Search form
    search_form = JournalEntrySearchForm(request.GET or None)

    if search_form.is_valid():
        journal_number = search_form.cleaned_data.get('journal_number')
        if journal_number:
            journals = journals.filter(journal_number__icontains=journal_number)

        entry_type = search_form.cleaned_data.get('entry_type')
        if entry_type:
            journals = journals.filter(entry_type=entry_type)

        status = search_form.cleaned_data.get('status')
        if status:
            journals = journals.filter(status=status)

        date_from = search_form.cleaned_data.get('date_from')
        date_to = search_form.cleaned_data.get('date_to')
        if date_from and date_to:
            journals = journals.filter(transaction_date__range=[date_from, date_to])

        branch = search_form.cleaned_data.get('branch')
        if branch:
            journals = journals.filter(branch=branch)

    journals = journals.order_by('-transaction_date', '-created_at')

    # Summary statistics
    total_count = journals.count()
    unposted_count = journals.filter(status__in=['draft', 'pending']).count()

    # Pagination
    paginator = Paginator(journals, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': 'Journal Entries',
        'journals': page_obj,
        'search_form': search_form,
        'total_count': total_count,
        'unposted_count': unposted_count,
    }

    return render(request, 'accounting/journal_entry_list.html', context)


@login_required
def journal_entry_detail(request, entry_id):
    """
    Display journal entry details with all lines

    Permissions: Staff (own), Manager (branch), Director/Admin (all)
    """
    checker = PermissionChecker(request.user)

    journal = get_object_or_404(
        JournalEntry.objects.select_related(
            'branch', 'created_by', 'posted_by', 'transaction', 'loan', 'savings_account'
        ).prefetch_related('lines__account', 'lines__client'),
        id=entry_id
    )

    # Permission check
    if checker.is_staff() and journal.created_by != request.user:
        messages.error(request, 'You can only view your own journal entries.')
        raise PermissionDenied
    elif checker.is_manager() and journal.branch != request.user.branch:
        messages.error(request, 'You can only view journal entries from your branch.')
        raise PermissionDenied

    # Calculate totals
    total_debits = journal.get_total_debits()
    total_credits = journal.get_total_credits()
    is_balanced = total_debits == total_credits

    context = {
        'page_title': f'Journal Entry: {journal.journal_number}',
        'journal': journal,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'is_balanced': is_balanced,
    }

    return render(request, 'accounting/journal_entry_detail.html', context)


@login_required
@db_transaction.atomic
def journal_entry_create(request):
    """
    Create manual journal entry with lines

    Permissions: Manager, Director, Admin with accounting permissions
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_director() or checker.is_admin()):
        messages.error(request, 'You do not have permission to create journal entries.')
        raise PermissionDenied

    if request.method == 'POST':
        form = JournalEntryForm(request.POST)
        formset = JournalEntryLineFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            try:
                # Validate balance
                total_debits = sum(
                    f.cleaned_data.get('debit_amount', Decimal('0'))
                    for f in formset
                    if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
                )
                total_credits = sum(
                    f.cleaned_data.get('credit_amount', Decimal('0'))
                    for f in formset
                    if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
                )

                if total_debits != total_credits:
                    messages.error(
                        request,
                        f'Journal entry not balanced! Debits: ₦{total_debits:,.2f} != Credits: ₦{total_credits:,.2f}'
                    )
                else:
                    # Create journal entry
                    journal = form.save(commit=False)
                    journal.created_by = request.user
                    journal.status = 'draft'  # Manual entries start as draft
                    journal.save()

                    # Save lines
                    formset.instance = journal
                    formset.save()

                    messages.success(
                        request,
                        f'Journal entry {journal.journal_number} created successfully! Status: Draft'
                    )
                    return redirect('core:journal_entry_detail', entry_id=journal.id)
            except ValidationError as e:
                messages.error(request, f'Validation error: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = JournalEntryForm()
        formset = JournalEntryLineFormSet()

    context = {
        'page_title': 'Create Manual Journal Entry',
        'form': form,
        'formset': formset,
    }

    return render(request, 'accounting/journal_entry_form.html', context)


@login_required
@db_transaction.atomic
def journal_entry_post(request, entry_id):
    """
    Post/approve a draft or pending journal entry

    Permissions: Director, Admin only
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_director() or checker.is_admin()):
        messages.error(request, 'Only Directors and Administrators can post journal entries.')
        raise PermissionDenied

    journal = get_object_or_404(JournalEntry, id=entry_id)

    if journal.status == 'posted':
        messages.warning(request, 'This journal entry is already posted.')
        return redirect('core:journal_entry_detail', entry_id=journal.id)

    if journal.status == 'reversed':
        messages.error(request, 'Cannot post a reversed journal entry.')
        return redirect('core:journal_entry_detail', entry_id=journal.id)

    if request.method == 'POST':
        # Validate balance
        total_debits = journal.get_total_debits()
        total_credits = journal.get_total_credits()

        if total_debits != total_credits:
            messages.error(
                request,
                f'Cannot post unbalanced journal! Debits: ₦{total_debits:,.2f} != Credits: ₦{total_credits:,.2f}'
            )
            return redirect('core:journal_entry_detail', entry_id=journal.id)

        # Post the journal
        journal.status = 'posted'
        journal.posted_by = request.user
        journal.posted_at = timezone.now()
        journal.posting_date = timezone.now().date()
        journal.save(update_fields=['status', 'posted_by', 'posted_at', 'posting_date', 'updated_at'])

        messages.success(request, f'Journal entry {journal.journal_number} posted successfully!')
        return redirect('core:journal_entry_detail', entry_id=journal.id)

    context = {
        'page_title': f'Post Journal Entry: {journal.journal_number}',
        'journal': journal,
        'total_debits': journal.get_total_debits(),
        'total_credits': journal.get_total_credits(),
    }

    return render(request, 'accounting/journal_entry_post_confirm.html', context)


@login_required
@db_transaction.atomic
def journal_entry_reverse(request, entry_id):
    """
    Reverse a posted journal entry

    Permissions: Director, Admin only
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_director() or checker.is_admin()):
        messages.error(request, 'Only Directors and Administrators can reverse journal entries.')
        raise PermissionDenied

    journal = get_object_or_404(JournalEntry, id=entry_id)

    if journal.status != 'posted':
        messages.error(request, 'Only posted journal entries can be reversed.')
        return redirect('core:journal_entry_detail', entry_id=journal.id)

    if journal.status == 'reversed':
        messages.warning(request, 'This journal entry has already been reversed.')
        return redirect('core:journal_entry_detail', entry_id=journal.id)

    if request.method == 'POST':
        form = JournalReversalForm(request.POST)

        if form.is_valid():
            reversal_reason = form.cleaned_data['reversal_reason']
            reversal_date = form.cleaned_data['reversal_date']

            # Create reversal entry with opposite signs
            lines = []
            for line in journal.lines.all():
                lines.append({
                    'account_code': line.account.gl_code,
                    'debit': line.credit_amount,  # Swap
                    'credit': line.debit_amount,  # Swap
                    'description': f'Reversal of {journal.journal_number}: {line.description}',
                    'client': line.client
                })

            # Create reversal journal
            reversal_journal = create_journal_entry(
                entry_type='reversal',
                transaction_date=reversal_date,
                branch=journal.branch,
                description=f'REVERSAL of {journal.journal_number}: {reversal_reason}',
                created_by=request.user,
                lines=lines,
                reference_number=f'REV-{journal.journal_number}',
                auto_post=True  # Auto-post reversals
            )

            # Update original journal status
            journal.status = 'reversed'
            journal.save(update_fields=['status', 'updated_at'])

            messages.success(
                request,
                f'Journal entry {journal.journal_number} reversed successfully! '
                f'Reversal entry: {reversal_journal.journal_number}'
            )
            return redirect('core:journal_entry_detail', entry_id=reversal_journal.id)
    else:
        form = JournalReversalForm()

    context = {
        'page_title': f'Reverse Journal Entry: {journal.journal_number}',
        'journal': journal,
        'form': form,
    }

    return render(request, 'accounting/journal_entry_reverse_form.html', context)


# =============================================================================
# FINANCIAL REPORTS VIEWS
# =============================================================================

@login_required
def report_trial_balance(request):
    """
    Generate Trial Balance Report

    Permissions: Manager, Director, Admin
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_director() or checker.is_admin()):
        messages.error(request, 'You do not have permission to view financial reports.')
        raise PermissionDenied

    form = TrialBalanceForm(request.GET or None)
    report_data = None

    if form.is_valid():
        date_from = form.cleaned_data['date_from']
        date_to = form.cleaned_data['date_to']
        branch = form.cleaned_data.get('branch')
        account_type = form.cleaned_data.get('account_type')
        show_zero_balances = form.cleaned_data.get('show_zero_balances', False)

        # Get all accounts
        accounts = ChartOfAccounts.objects.filter(is_active=True).select_related('account_type')

        if account_type:
            accounts = accounts.filter(account_type__name=account_type)

        # Calculate balances for each account
        trial_balance = []
        total_debits = Decimal('0')
        total_credits = Decimal('0')

        for account in accounts.order_by('gl_code'):
            # Filter journal lines by date range and branch
            journal_lines = account.journal_lines.filter(
                journal_entry__status='posted',
                journal_entry__transaction_date__range=[date_from, date_to]
            )

            if branch:
                journal_lines = journal_lines.filter(journal_entry__branch=branch)

            debit_sum = journal_lines.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
            credit_sum = journal_lines.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')

            # Calculate net balance
            if account.account_type.normal_balance == 'debit':
                net_debit = debit_sum - credit_sum if debit_sum > credit_sum else Decimal('0')
                net_credit = credit_sum - debit_sum if credit_sum > debit_sum else Decimal('0')
            else:
                net_credit = credit_sum - debit_sum if credit_sum > debit_sum else Decimal('0')
                net_debit = debit_sum - credit_sum if debit_sum > credit_sum else Decimal('0')

            # Skip zero balances if requested
            if not show_zero_balances and net_debit == 0 and net_credit == 0:
                continue

            trial_balance.append({
                'account': account,
                'debit': net_debit,
                'credit': net_credit
            })

            total_debits += net_debit
            total_credits += net_credit

        report_data = {
            'trial_balance': trial_balance,
            'total_debits': total_debits,
            'total_credits': total_credits,
            'is_balanced': total_debits == total_credits,
            'difference': total_debits - total_credits,
            'date_from': date_from,
            'date_to': date_to,
            'branch': branch,
            'show_zero_balances': show_zero_balances,
        }

        # Handle exports
        export_format = request.GET.get('export')
        if export_format == 'pdf':
            return generate_trial_balance_pdf(report_data, form.cleaned_data)
        elif export_format == 'excel':
            return export_trial_balance_excel(report_data, form.cleaned_data)

    context = {
        'page_title': 'Trial Balance',
        'form': form,
        'report_data': report_data,
    }

    return render(request, 'accounting/report_trial_balance.html', context)


@login_required
def report_profit_loss(request):
    """
    Generate Profit & Loss Statement

    Permissions: Manager, Director, Admin
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_director() or checker.is_admin()):
        messages.error(request, 'You do not have permission to view financial reports.')
        raise PermissionDenied

    form = ProfitLossForm(request.GET or None)
    report_data = None

    if form.is_valid():
        date_from = form.cleaned_data['date_from']
        date_to = form.cleaned_data['date_to']
        branch = form.cleaned_data.get('branch')

        # Get income accounts (4000-4999)
        income_accounts = ChartOfAccounts.objects.filter(
            account_type__name=AccountType.INCOME,
            is_active=True
        ).order_by('gl_code')

        # Get expense accounts (5000-5999)
        expense_accounts = ChartOfAccounts.objects.filter(
            account_type__name=AccountType.EXPENSE,
            is_active=True
        ).order_by('gl_code')

        # Calculate income
        income_items = []
        total_income = Decimal('0')

        for account in income_accounts:
            journal_lines = account.journal_lines.filter(
                journal_entry__status='posted',
                journal_entry__transaction_date__range=[date_from, date_to]
            )

            if branch:
                journal_lines = journal_lines.filter(journal_entry__branch=branch)

            credit_sum = journal_lines.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')
            debit_sum = journal_lines.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
            amount = credit_sum - debit_sum  # Income increases with credit

            if amount != 0:
                income_items.append({'account': account, 'amount': amount})
                total_income += amount

        # Calculate expenses
        expense_items = []
        total_expenses = Decimal('0')

        for account in expense_accounts:
            journal_lines = account.journal_lines.filter(
                journal_entry__status='posted',
                journal_entry__transaction_date__range=[date_from, date_to]
            )

            if branch:
                journal_lines = journal_lines.filter(journal_entry__branch=branch)

            debit_sum = journal_lines.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
            credit_sum = journal_lines.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')
            amount = debit_sum - credit_sum  # Expense increases with debit

            if amount != 0:
                expense_items.append({'account': account, 'amount': amount})
                total_expenses += amount

        # Calculate net profit/loss
        net_profit = total_income - total_expenses

        report_data = {
            'income_items': income_items,
            'expense_items': expense_items,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
            'date_from': date_from,
            'date_to': date_to,
            'branch': branch,
        }

        # Handle exports
        export_format = request.GET.get('export')
        if export_format == 'pdf':
            return generate_profit_loss_pdf(report_data, form.cleaned_data)
        elif export_format == 'excel':
            return export_profit_loss_excel(report_data, form.cleaned_data)

    context = {
        'page_title': 'Profit & Loss Statement',
        'form': form,
        'report_data': report_data,
    }

    return render(request, 'accounting/report_profit_loss.html', context)


@login_required
def report_balance_sheet(request):
    """
    Generate Balance Sheet

    Permissions: Manager, Director, Admin
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_director() or checker.is_admin()):
        messages.error(request, 'You do not have permission to view financial reports.')
        raise PermissionDenied

    form = BalanceSheetForm(request.GET or None)
    report_data = None

    if form.is_valid():
        as_of_date = form.cleaned_data['as_of_date']
        branch = form.cleaned_data.get('branch')

        # Helper function to calculate account balance
        def calc_balance(account, as_of):
            lines = account.journal_lines.filter(
                journal_entry__status='posted',
                journal_entry__transaction_date__lte=as_of
            )

            if branch:
                lines = lines.filter(journal_entry__branch=branch)

            debit_sum = lines.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
            credit_sum = lines.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')

            if account.account_type.normal_balance == 'debit':
                return debit_sum - credit_sum
            else:
                return credit_sum - debit_sum

        # Get assets
        asset_accounts = ChartOfAccounts.objects.filter(
            account_type__name=AccountType.ASSET,
            is_active=True
        ).order_by('gl_code')

        assets = []
        total_assets = Decimal('0')
        for account in asset_accounts:
            balance = calc_balance(account, as_of_date)
            if balance != 0:
                assets.append({'account': account, 'balance': balance})
                total_assets += balance

        # Get liabilities
        liability_accounts = ChartOfAccounts.objects.filter(
            account_type__name=AccountType.LIABILITY,
            is_active=True
        ).order_by('gl_code')

        liabilities = []
        total_liabilities = Decimal('0')
        for account in liability_accounts:
            balance = calc_balance(account, as_of_date)
            if balance != 0:
                liabilities.append({'account': account, 'balance': balance})
                total_liabilities += balance

        # Get equity
        equity_accounts = ChartOfAccounts.objects.filter(
            account_type__name=AccountType.EQUITY,
            is_active=True
        ).order_by('gl_code')

        equity = []
        total_equity = Decimal('0')
        for account in equity_accounts:
            balance = calc_balance(account, as_of_date)
            if balance != 0:
                equity.append({'account': account, 'balance': balance})
                total_equity += balance

        # Calculate retained earnings (cumulative P&L)
        # This would be more complex in a real system
        # For now, just calculate the difference to balance
        total_liabilities_equity = total_liabilities + total_equity

        report_data = {
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'total_equity': total_equity,
            'total_liabilities_equity': total_liabilities_equity,
            'is_balanced': abs(total_assets - total_liabilities_equity) < Decimal('0.01'),
            'as_of_date': as_of_date,
            'branch': branch,
        }

        # Handle exports
        export_format = request.GET.get('export')
        if export_format == 'pdf':
            return generate_balance_sheet_pdf(report_data, form.cleaned_data)
        elif export_format == 'excel':
            return export_balance_sheet_excel(report_data, form.cleaned_data)

    context = {
        'page_title': 'Balance Sheet',
        'form': form,
        'report_data': report_data,
    }

    return render(request, 'accounting/report_balance_sheet.html', context)


@login_required
def report_general_ledger(request):
    """
    Generate General Ledger for specific account

    Permissions: Manager, Director, Admin
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_director() or checker.is_admin()):
        messages.error(request, 'You do not have permission to view financial reports.')
        raise PermissionDenied

    form = GeneralLedgerForm(request.GET or None)
    report_data = None

    if form.is_valid():
        account = form.cleaned_data['account']
        date_from = form.cleaned_data['date_from']
        date_to = form.cleaned_data['date_to']
        branch = form.cleaned_data.get('branch')
        show_running_balance = form.cleaned_data.get('show_running_balance', True)

        # Get journal lines for this account
        lines = account.journal_lines.filter(
            journal_entry__status='posted',
            journal_entry__transaction_date__range=[date_from, date_to]
        ).select_related(
            'journal_entry', 'journal_entry__branch', 'client'
        ).order_by('journal_entry__transaction_date', 'journal_entry__created_at')

        if branch:
            lines = lines.filter(journal_entry__branch=branch)

        # Calculate opening balance
        opening_lines = account.journal_lines.filter(
            journal_entry__status='posted',
            journal_entry__transaction_date__lt=date_from
        )

        if branch:
            opening_lines = opening_lines.filter(journal_entry__branch=branch)

        opening_debit = opening_lines.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
        opening_credit = opening_lines.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')

        if account.account_type.normal_balance == 'debit':
            opening_balance = opening_debit - opening_credit
        else:
            opening_balance = opening_credit - opening_debit

        # Process lines with running balance
        transactions = []
        running_balance = opening_balance

        for line in lines:
            if account.account_type.normal_balance == 'debit':
                running_balance += line.debit_amount - line.credit_amount
            else:
                running_balance += line.credit_amount - line.debit_amount

            transactions.append({
                'line': line,
                'running_balance': running_balance if show_running_balance else None
            })

        report_data = {
            'account': account,
            'opening_balance': opening_balance,
            'transactions': transactions,
            'closing_balance': running_balance,
            'date_from': date_from,
            'date_to': date_to,
            'branch': branch,
        }

        # Handle exports
        export_format = request.GET.get('export')
        if export_format == 'pdf':
            return generate_general_ledger_pdf(report_data, form.cleaned_data)
        elif export_format == 'excel':
            return export_general_ledger_excel(report_data, form.cleaned_data)

    context = {
        'page_title': 'General Ledger',
        'form': form,
        'report_data': report_data,
    }

    return render(request, 'accounting/report_general_ledger.html', context)


@login_required
def report_cash_flow(request):
    """
    Generate Cash Flow Statement (simplified)

    Permissions: Manager, Director, Admin
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_director() or checker.is_admin()):
        messages.error(request, 'You do not have permission to view financial reports.')
        raise PermissionDenied

    form = DateRangeForm(request.GET or None)
    report_data = None

    if form.is_valid():
        date_from = form.cleaned_data['date_from']
        date_to = form.cleaned_data['date_to']

        # Get cash account (1010)
        try:
            cash_account = ChartOfAccounts.objects.get(gl_code='1010', is_active=True)

            # Get all cash movements
            cash_lines = cash_account.journal_lines.filter(
                journal_entry__status='posted',
                journal_entry__transaction_date__range=[date_from, date_to]
            ).select_related('journal_entry').order_by('journal_entry__transaction_date')

            # Categorize by transaction type
            operating_activities = []
            investing_activities = []
            financing_activities = []

            operating_total = Decimal('0')
            investing_total = Decimal('0')
            financing_total = Decimal('0')

            for line in cash_lines:
                amount = line.debit_amount - line.credit_amount
                entry_type = line.journal_entry.entry_type

                if entry_type in ['loan_repayment', 'savings_deposit', 'savings_withdrawal', 'fee_collection']:
                    operating_activities.append({'line': line, 'amount': amount})
                    operating_total += amount
                elif entry_type in ['loan_disbursement']:
                    investing_activities.append({'line': line, 'amount': amount})
                    investing_total += amount
                else:
                    financing_activities.append({'line': line, 'amount': amount})
                    financing_total += amount

            net_cash_flow = operating_total + investing_total + financing_total

            report_data = {
                'operating_activities': operating_activities,
                'investing_activities': investing_activities,
                'financing_activities': financing_activities,
                'operating_total': operating_total,
                'investing_total': investing_total,
                'financing_total': financing_total,
                'net_cash_flow': net_cash_flow,
                'date_from': date_from,
                'date_to': date_to,
            }

            # Handle exports
            export_format = request.GET.get('export')
            if export_format == 'pdf':
                return generate_cash_flow_pdf(report_data, form.cleaned_data)
            elif export_format == 'excel':
                return export_cash_flow_excel(report_data, form.cleaned_data)

        except ChartOfAccounts.DoesNotExist:
            messages.error(request, 'Cash account (1010) not found. Please initialize Chart of Accounts.')

    context = {
        'page_title': 'Cash Flow Statement',
        'form': form,
        'report_data': report_data,
    }

    return render(request, 'accounting/report_cash_flow.html', context)


@login_required
def report_transaction_audit(request):
    """
    Transaction Audit Report - shows all transactions with journal entry links

    Permissions: Director, Admin only
    """
    checker = PermissionChecker(request.user)

    if not (checker.is_director() or checker.is_admin()):
        messages.error(request, 'Only Directors and Administrators can view audit reports.')
        raise PermissionDenied

    # Get all completed transactions
    transactions = Transaction.objects.filter(
        status='completed'
    ).select_related(
        'client', 'branch', 'processed_by', 'loan', 'savings_account'
    ).prefetch_related('journal_entries').order_by('-transaction_date')

    # Apply filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if date_from and date_to:
        transactions = transactions.filter(transaction_date__range=[date_from, date_to])

    transaction_type = request.GET.get('transaction_type')
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)

    # Identify transactions without journal entries (AUDIT ALERT)
    audit_data = []
    missing_journal_count = 0

    for txn in transactions[:200]:  # Limit for performance
        journal_entries = txn.journal_entries.all()
        has_journal = journal_entries.exists()

        if not has_journal:
            missing_journal_count += 1

        audit_data.append({
            'transaction': txn,
            'has_journal': has_journal,
            'journal_entries': journal_entries
        })

    report_data = {
        'audit_data': audit_data,
        'missing_journal_count': missing_journal_count,
        'total_transactions': transactions.count(),
        'date_from': date_from,
        'date_to': date_to,
    }

    # Handle exports
    export_format = request.GET.get('export')
    if export_format == 'pdf':
        return generate_transaction_audit_pdf(report_data, request.GET)
    elif export_format == 'excel':
        return export_transaction_audit_excel(report_data, request.GET)

    context = {
        'page_title': 'Transaction Audit Log',
        'audit_data': audit_data,
        'missing_journal_count': missing_journal_count,
        'total_transactions': transactions.count(),
    }

    return render(request, 'accounting/report_transaction_audit.html', context)
