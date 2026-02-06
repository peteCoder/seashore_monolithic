"""
Accounting Helper Functions for Seashore Microfinance

This module provides utility functions for automatic journal entry creation
following double-entry bookkeeping principles.

Every financial transaction MUST create a corresponding journal entry to ensure:
- Complete audit trail
- Accurate financial reporting
- Balance sheet integrity
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def validate_journal_balance(lines):
    """
    Validate that total debits equal total credits

    Args:
        lines: List of dicts with 'debit' and 'credit' keys

    Raises:
        ValidationError: If debits != credits
    """
    total_debits = sum(Decimal(str(line.get('debit', 0))) for line in lines)
    total_credits = sum(Decimal(str(line.get('credit', 0))) for line in lines)

    if total_debits != total_credits:
        raise ValidationError(
            f"Journal entry not balanced: Debits ₦{total_debits:,.2f} != Credits ₦{total_credits:,.2f}"
        )


def get_cash_account_for_branch(branch):
    """
    Get the primary cash account for a branch

    Args:
        branch: Branch object

    Returns:
        ChartOfAccounts: Cash In Hand account (1010) or branch-specific cash account
    """
    from core.models import ChartOfAccounts

    # Try to get branch-specific cash account first
    cash_account = ChartOfAccounts.objects.filter(
        gl_code='1010',
        branch=branch,
        is_active=True
    ).first()

    # Fall back to system-wide cash account
    if not cash_account:
        cash_account = ChartOfAccounts.objects.filter(
            gl_code='1010',
            branch__isnull=True,
            is_active=True
        ).first()

    if not cash_account:
        raise ValidationError("Cash account (1010) not found. Please initialize Chart of Accounts.")

    return cash_account


def get_savings_liability_account(product_type):
    """
    Map savings product type to liability account

    Args:
        product_type: 'regular', 'fixed', 'target', or 'children'

    Returns:
        ChartOfAccounts: Appropriate savings liability account
    """
    from core.models import ChartOfAccounts

    account_mapping = {
        'regular': '2010',   # Savings Deposits - Regular
        'fixed': '2020',     # Savings Deposits - Fixed
        'target': '2030',    # Savings Deposits - Target
        'children': '2040',  # Savings Deposits - Children
    }

    gl_code = account_mapping.get(product_type, '2010')  # Default to regular

    account = ChartOfAccounts.objects.filter(
        gl_code=gl_code,
        is_active=True
    ).first()

    if not account:
        raise ValidationError(f"Savings liability account ({gl_code}) not found.")

    return account


@transaction.atomic
def create_journal_entry(
    entry_type,
    transaction_date,
    branch,
    description,
    created_by,
    lines,
    transaction_obj=None,
    loan=None,
    savings_account=None,
    reference_number='',
    auto_post=True
):
    """
    Master function for creating journal entries with validation

    Args:
        entry_type: Type of journal entry (e.g., 'loan_disbursement', 'savings_deposit')
        transaction_date: Date of the transaction
        branch: Branch where transaction occurred
        description: Journal entry description
        created_by: User creating the entry
        lines: List of dicts with format:
               [{'account_code': '1010', 'debit': 1000.00, 'credit': 0, 'description': '...', 'client': client_obj}]
        transaction_obj: Related Transaction object (optional)
        loan: Related Loan object (optional)
        savings_account: Related SavingsAccount object (optional)
        reference_number: External reference (optional)
        auto_post: Auto-post for system-generated entries (default: True)

    Returns:
        JournalEntry: Created journal entry object

    Raises:
        ValidationError: If validation fails
    """
    from core.models import ChartOfAccounts, JournalEntry, JournalEntryLine

    # Validate minimum lines
    if len(lines) < 2:
        raise ValidationError("Journal entry must have at least 2 lines")

    # Validate balance
    validate_journal_balance(lines)

    # Create journal entry header
    journal = JournalEntry.objects.create(
        entry_type=entry_type,
        transaction_date=transaction_date,
        branch=branch,
        description=description,
        reference_number=reference_number,
        created_by=created_by,
        transaction=transaction_obj,
        loan=loan,
        savings_account=savings_account,
        status='draft' if not auto_post else 'posted',
        posted_by=created_by if auto_post else None,
        posted_at=timezone.now() if auto_post else None,
        posting_date=transaction_date if auto_post else None
    )

    # Create journal entry lines
    for line_data in lines:
        # Get account
        account = ChartOfAccounts.objects.filter(
            gl_code=line_data['account_code'],
            is_active=True
        ).first()

        if not account:
            raise ValidationError(f"Account {line_data['account_code']} not found or inactive")

        # Validate only debit OR credit
        debit = Decimal(str(line_data.get('debit', 0)))
        credit = Decimal(str(line_data.get('credit', 0)))

        if debit > 0 and credit > 0:
            raise ValidationError("Line cannot have both debit and credit amounts")

        if debit == 0 and credit == 0:
            raise ValidationError("Line must have either debit or credit amount")

        # Create line
        JournalEntryLine.objects.create(
            journal_entry=journal,
            account=account,
            debit_amount=debit,
            credit_amount=credit,
            description=line_data.get('description', description),
            client=line_data.get('client')
        )

    logger.info(
        f"Journal entry created: {journal.journal_number} | "
        f"Type: {entry_type} | Amount: ₦{journal.get_total_debits():,.2f}"
    )

    return journal


def post_loan_disbursement_journal(loan, disbursed_by):
    """
    Create journal entry for loan disbursement

    Journal Entry:
        Dr  1810 Loan Receivable - Principal     xxx
            Cr  1010 Cash In Hand                    xxx

    Args:
        loan: Loan object
        disbursed_by: User who disbursed the loan

    Returns:
        JournalEntry: Created journal entry
    """
    cash_account = get_cash_account_for_branch(loan.branch)

    lines = [
        {
            'account_code': '1810',  # Loan Receivable - Principal
            'debit': loan.principal_amount,
            'credit': 0,
            'description': f"Loan disbursement to {loan.client.get_full_name()}",
            'client': loan.client
        },
        {
            'account_code': cash_account.gl_code,  # Cash In Hand
            'debit': 0,
            'credit': loan.principal_amount,
            'description': f"Cash paid for loan {loan.loan_number}",
            'client': loan.client
        }
    ]

    return create_journal_entry(
        entry_type='loan_disbursement',
        transaction_date=loan.disbursement_date or timezone.now().date(),
        branch=loan.branch,
        description=f"Loan Disbursement: {loan.loan_number}",
        created_by=disbursed_by,
        lines=lines,
        loan=loan,
        reference_number=loan.loan_number,
        auto_post=True
    )


def post_loan_repayment_journal(
    loan,
    amount,
    principal_portion,
    interest_portion,
    processed_by,
    transaction_obj
):
    """
    Create journal entry for loan repayment

    Journal Entry:
        Dr  1010 Cash In Hand                    xxx
            Cr  1810 Loan Receivable - Principal    [principal]
            Cr  4010 Interest Income - Loans        [interest]

    Args:
        loan: Loan object
        amount: Total repayment amount
        principal_portion: Principal component
        interest_portion: Interest component
        processed_by: User processing the repayment
        transaction_obj: Transaction object

    Returns:
        JournalEntry: Created journal entry
    """
    cash_account = get_cash_account_for_branch(loan.branch)

    lines = [
        {
            'account_code': cash_account.gl_code,  # Cash In Hand
            'debit': amount,
            'credit': 0,
            'description': f"Loan repayment from {loan.client.get_full_name()}",
            'client': loan.client
        }
    ]

    # Add principal portion
    if principal_portion > 0:
        lines.append({
            'account_code': '1810',  # Loan Receivable - Principal
            'debit': 0,
            'credit': principal_portion,
            'description': f"Principal repayment for loan {loan.loan_number}",
            'client': loan.client
        })

    # Add interest portion
    if interest_portion > 0:
        lines.append({
            'account_code': '4010',  # Interest Income - Loans
            'debit': 0,
            'credit': interest_portion,
            'description': f"Interest income from loan {loan.loan_number}",
            'client': loan.client
        })

    return create_journal_entry(
        entry_type='loan_repayment',
        transaction_date=transaction_obj.transaction_date,
        branch=loan.branch,
        description=f"Loan Repayment: {loan.loan_number}",
        created_by=processed_by,
        lines=lines,
        transaction_obj=transaction_obj,
        loan=loan,
        reference_number=transaction_obj.transaction_ref,
        auto_post=True
    )


def post_savings_deposit_journal(
    savings_account,
    amount,
    processed_by,
    transaction_obj
):
    """
    Create journal entry for savings deposit

    Journal Entry:
        Dr  1010 Cash In Hand                    xxx
            Cr  20xx Savings Deposits - [Type]      xxx

    Args:
        savings_account: SavingsAccount object
        amount: Deposit amount
        processed_by: User processing the deposit
        transaction_obj: Transaction object

    Returns:
        JournalEntry: Created journal entry
    """
    cash_account = get_cash_account_for_branch(savings_account.branch)
    savings_liability = get_savings_liability_account(
        savings_account.savings_product.product_type
    )

    lines = [
        {
            'account_code': cash_account.gl_code,  # Cash In Hand
            'debit': amount,
            'credit': 0,
            'description': f"Savings deposit from {savings_account.client.get_full_name()}",
            'client': savings_account.client
        },
        {
            'account_code': savings_liability.gl_code,  # Savings Deposits - [Type]
            'debit': 0,
            'credit': amount,
            'description': f"Deposit to account {savings_account.account_number}",
            'client': savings_account.client
        }
    ]

    return create_journal_entry(
        entry_type='savings_deposit',
        transaction_date=transaction_obj.transaction_date,
        branch=savings_account.branch,
        description=f"Savings Deposit: {savings_account.account_number}",
        created_by=processed_by,
        lines=lines,
        transaction_obj=transaction_obj,
        savings_account=savings_account,
        reference_number=transaction_obj.transaction_ref,
        auto_post=True
    )


def post_savings_withdrawal_journal(
    savings_account,
    amount,
    processed_by,
    transaction_obj
):
    """
    Create journal entry for savings withdrawal

    Journal Entry:
        Dr  20xx Savings Deposits - [Type]      xxx
            Cr  1010 Cash In Hand                   xxx

    Args:
        savings_account: SavingsAccount object
        amount: Withdrawal amount
        processed_by: User processing the withdrawal
        transaction_obj: Transaction object

    Returns:
        JournalEntry: Created journal entry
    """
    cash_account = get_cash_account_for_branch(savings_account.branch)
    savings_liability = get_savings_liability_account(
        savings_account.savings_product.product_type
    )

    lines = [
        {
            'account_code': savings_liability.gl_code,  # Savings Deposits - [Type]
            'debit': amount,
            'credit': 0,
            'description': f"Withdrawal from account {savings_account.account_number}",
            'client': savings_account.client
        },
        {
            'account_code': cash_account.gl_code,  # Cash In Hand
            'debit': 0,
            'credit': amount,
            'description': f"Cash paid to {savings_account.client.get_full_name()}",
            'client': savings_account.client
        }
    ]

    return create_journal_entry(
        entry_type='savings_withdrawal',
        transaction_date=transaction_obj.transaction_date,
        branch=savings_account.branch,
        description=f"Savings Withdrawal: {savings_account.account_number}",
        created_by=processed_by,
        lines=lines,
        transaction_obj=transaction_obj,
        savings_account=savings_account,
        reference_number=transaction_obj.transaction_ref,
        auto_post=True
    )


def post_fee_collection_journal(
    fee_type,
    amount,
    client,
    branch,
    processed_by,
    transaction_obj
):
    """
    Create journal entry for fee collection

    Journal Entry:
        Dr  1010 Cash In Hand                    xxx
            Cr  41xx Fee Income (varies by type)    xxx

    Args:
        fee_type: Type of fee (e.g., 'registration_fee', 'loan_insurance_fee')
        amount: Fee amount
        client: Client object
        branch: Branch object
        processed_by: User processing the fee
        transaction_obj: Transaction object

    Returns:
        JournalEntry: Created journal entry
    """
    # Map fee types to income accounts
    fee_account_mapping = {
        'registration_fee': '4110',
        'loan_form_fee': '4120',
        'loan_insurance_fee': '4130',
        'processing_fee': '4140',
        'risk_premium': '4150',
        'tech_fee': '4160',
        'late_payment_fee': '4170',
    }

    income_account_code = fee_account_mapping.get(fee_type, '4110')  # Default to registration
    cash_account = get_cash_account_for_branch(branch)

    lines = [
        {
            'account_code': cash_account.gl_code,  # Cash In Hand
            'debit': amount,
            'credit': 0,
            'description': f"{fee_type.replace('_', ' ').title()} from {client.get_full_name()}",
            'client': client
        },
        {
            'account_code': income_account_code,  # Fee Income
            'debit': 0,
            'credit': amount,
            'description': f"{fee_type.replace('_', ' ').title()} income",
            'client': client
        }
    ]

    return create_journal_entry(
        entry_type='fee_collection',
        transaction_date=transaction_obj.transaction_date,
        branch=branch,
        description=f"Fee Collection: {fee_type.replace('_', ' ').title()}",
        created_by=processed_by,
        lines=lines,
        transaction_obj=transaction_obj,
        reference_number=transaction_obj.transaction_ref,
        auto_post=True
    )
