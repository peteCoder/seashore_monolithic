"""
Management command to initialize the Chart of Accounts for Seashore Microfinance

This command creates:
- Account Types (Asset, Liability, Equity, Income, Expense)
- Account Categories (sub-classifications)
- Chart of Accounts entries (GL accounts)

Usage:
    python manage.py init_chart_of_accounts
    python manage.py init_chart_of_accounts --reset  # Delete existing and recreate
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import AccountType, AccountCategory, ChartOfAccounts


class Command(BaseCommand):
    help = 'Initialize the Chart of Accounts with standard microfinance accounts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing accounts and recreate from scratch',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options['reset']

        if reset:
            self.stdout.write(self.style.WARNING('Deleting existing accounts...'))
            ChartOfAccounts.objects.all().delete()
            AccountCategory.objects.all().delete()
            AccountType.objects.all().delete()

        self.stdout.write(self.style.SUCCESS('\n=== Initializing Chart of Accounts ===\n'))

        # Create Account Types
        self.create_account_types()

        # Create Account Categories
        self.create_account_categories()

        # Create Chart of Accounts
        self.create_chart_of_accounts()

        self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Chart of Accounts initialized successfully!\n'))

    def create_account_types(self):
        """Create the five main account types"""
        self.stdout.write('Creating Account Types...')

        account_types = [
            {
                'name': AccountType.ASSET,
                'normal_balance': 'debit',
                'description': 'Resources owned by the organization (cash, receivables, assets)'
            },
            {
                'name': AccountType.LIABILITY,
                'normal_balance': 'credit',
                'description': 'Obligations owed to others (savings deposits, payables)'
            },
            {
                'name': AccountType.EQUITY,
                'normal_balance': 'credit',
                'description': 'Owner\'s stake in the business (capital, retained earnings)'
            },
            {
                'name': AccountType.INCOME,
                'normal_balance': 'credit',
                'description': 'Revenue earned from operations (interest income, fees)'
            },
            {
                'name': AccountType.EXPENSE,
                'normal_balance': 'debit',
                'description': 'Costs incurred in operations (salaries, rent, utilities)'
            },
        ]

        for type_data in account_types:
            account_type, created = AccountType.objects.get_or_create(
                name=type_data['name'],
                defaults={
                    'normal_balance': type_data['normal_balance'],
                    'description': type_data['description']
                }
            )
            if created:
                self.stdout.write(f'  [+] Created: {account_type.get_name_display()}')
            else:
                self.stdout.write(f'  [*] Exists: {account_type.get_name_display()}')

    def create_account_categories(self):
        """Create account categories (sub-classifications)"""
        self.stdout.write('\nCreating Account Categories...')

        # Get account types
        asset_type = AccountType.objects.get(name=AccountType.ASSET)
        liability_type = AccountType.objects.get(name=AccountType.LIABILITY)
        equity_type = AccountType.objects.get(name=AccountType.EQUITY)
        income_type = AccountType.objects.get(name=AccountType.INCOME)
        expense_type = AccountType.objects.get(name=AccountType.EXPENSE)

        categories = [
            # Asset Categories
            {'name': 'Cash & Bank', 'account_type': asset_type, 'code_prefix': '10',
             'description': 'Cash on hand and bank balances'},
            {'name': 'Loan Receivables', 'account_type': asset_type, 'code_prefix': '18',
             'description': 'Loans disbursed to clients'},
            {'name': 'Other Assets', 'account_type': asset_type, 'code_prefix': '19',
             'description': 'Fixed assets, prepaid expenses, etc.'},

            # Liability Categories
            {'name': 'Savings & Deposits', 'account_type': liability_type, 'code_prefix': '20',
             'description': 'Client savings deposits'},
            {'name': 'Interest Payable', 'account_type': liability_type, 'code_prefix': '21',
             'description': 'Interest owed on savings'},
            {'name': 'Other Liabilities', 'account_type': liability_type, 'code_prefix': '29',
             'description': 'Accounts payable, accrued expenses'},

            # Equity Categories
            {'name': 'Capital', 'account_type': equity_type, 'code_prefix': '30',
             'description': 'Share capital and retained earnings'},
            {'name': 'Current Year', 'account_type': equity_type, 'code_prefix': '31',
             'description': 'Current year profit or loss'},

            # Income Categories
            {'name': 'Interest Income', 'account_type': income_type, 'code_prefix': '40',
             'description': 'Interest earned from loans'},
            {'name': 'Fee Income', 'account_type': income_type, 'code_prefix': '41',
             'description': 'Fees collected from clients'},

            # Expense Categories
            {'name': 'Interest Expense', 'account_type': expense_type, 'code_prefix': '50',
             'description': 'Interest paid on savings'},
            {'name': 'Operating Expenses', 'account_type': expense_type, 'code_prefix': '51',
             'description': 'Salaries, rent, utilities'},
            {'name': 'Loan Loss Provisions', 'account_type': expense_type, 'code_prefix': '59',
             'description': 'Provision for bad debts'},
        ]

        for cat_data in categories:
            category, created = AccountCategory.objects.get_or_create(
                code_prefix=cat_data['code_prefix'],
                defaults={
                    'name': cat_data['name'],
                    'account_type': cat_data['account_type'],
                    'description': cat_data['description']
                }
            )
            if created:
                self.stdout.write(f'  [+] Created: {category.code_prefix} - {category.name}')
            else:
                self.stdout.write(f'  [*] Exists: {category.code_prefix} - {category.name}')

    def create_chart_of_accounts(self):
        """Create the actual GL accounts"""
        self.stdout.write('\nCreating Chart of Accounts...')

        # Get account types
        asset_type = AccountType.objects.get(name=AccountType.ASSET)
        liability_type = AccountType.objects.get(name=AccountType.LIABILITY)
        equity_type = AccountType.objects.get(name=AccountType.EQUITY)
        income_type = AccountType.objects.get(name=AccountType.INCOME)
        expense_type = AccountType.objects.get(name=AccountType.EXPENSE)

        # Get categories
        cash_cat = AccountCategory.objects.get(code_prefix='10')
        loan_cat = AccountCategory.objects.get(code_prefix='18')
        asset_other_cat = AccountCategory.objects.get(code_prefix='19')
        savings_cat = AccountCategory.objects.get(code_prefix='20')
        interest_payable_cat = AccountCategory.objects.get(code_prefix='21')
        liability_other_cat = AccountCategory.objects.get(code_prefix='29')
        capital_cat = AccountCategory.objects.get(code_prefix='30')
        current_year_cat = AccountCategory.objects.get(code_prefix='31')
        interest_income_cat = AccountCategory.objects.get(code_prefix='40')
        fee_income_cat = AccountCategory.objects.get(code_prefix='41')
        interest_expense_cat = AccountCategory.objects.get(code_prefix='50')
        operating_expense_cat = AccountCategory.objects.get(code_prefix='51')
        provision_cat = AccountCategory.objects.get(code_prefix='59')

        accounts = [
            # ====================================================================
            # ASSETS
            # ====================================================================

            # Cash & Bank (1000-1099)
            {
                'gl_code': '1010',
                'account_name': 'Cash In Hand',
                'account_type': asset_type,
                'account_category': cash_cat,
                'description': 'Physical cash held at branches',
                'is_control_account': False,
                'allows_manual_entries': True,
            },
            {
                'gl_code': '1020',
                'account_name': 'Cash at Bank - Main Operating Account',
                'account_type': asset_type,
                'account_category': cash_cat,
                'description': 'Primary bank account for operations',
                'is_control_account': False,
                'allows_manual_entries': True,
            },
            {
                'gl_code': '1030',
                'account_name': 'Cash at Bank - Savings Account',
                'account_type': asset_type,
                'account_category': cash_cat,
                'description': 'Bank savings account',
                'is_control_account': False,
                'allows_manual_entries': True,
            },
            {
                'gl_code': '1040',
                'account_name': 'Petty Cash',
                'account_type': asset_type,
                'account_category': cash_cat,
                'description': 'Small cash fund for minor expenses',
                'is_control_account': False,
                'allows_manual_entries': True,
            },

            # Loan Receivables (1800-1899)
            {
                'gl_code': '1810',
                'account_name': 'Loan Receivable - Principal',
                'account_type': asset_type,
                'account_category': loan_cat,
                'description': 'Outstanding loan principal from clients',
                'is_control_account': False,
                'allows_manual_entries': False,  # System-generated only
            },
            {
                'gl_code': '1820',
                'account_name': 'Interest Receivable - Loans',
                'account_type': asset_type,
                'account_category': loan_cat,
                'description': 'Accrued interest on loans',
                'is_control_account': False,
                'allows_manual_entries': False,
            },
            {
                'gl_code': '1830',
                'account_name': 'Loan Fees Receivable',
                'account_type': asset_type,
                'account_category': loan_cat,
                'description': 'Unpaid loan-related fees',
                'is_control_account': False,
                'allows_manual_entries': True,
            },

            # Other Assets (1900-1999)
            {
                'gl_code': '1910',
                'account_name': 'Prepaid Expenses',
                'account_type': asset_type,
                'account_category': asset_other_cat,
                'description': 'Expenses paid in advance',
                'is_control_account': False,
                'allows_manual_entries': True,
            },
            {
                'gl_code': '1920',
                'account_name': 'Fixed Assets',
                'account_type': asset_type,
                'account_category': asset_other_cat,
                'description': 'Property, equipment, furniture',
                'is_control_account': False,
                'allows_manual_entries': True,
            },

            # ====================================================================
            # LIABILITIES
            # ====================================================================

            # Savings & Deposits (2000-2099)
            {
                'gl_code': '2010',
                'account_name': 'Savings Deposits - Regular',
                'account_type': liability_type,
                'account_category': savings_cat,
                'description': 'Regular savings deposits from clients',
                'is_control_account': False,
                'allows_manual_entries': False,  # System-generated only
            },
            {
                'gl_code': '2020',
                'account_name': 'Savings Deposits - Fixed',
                'account_type': liability_type,
                'account_category': savings_cat,
                'description': 'Fixed term deposits from clients',
                'is_control_account': False,
                'allows_manual_entries': False,
            },
            {
                'gl_code': '2030',
                'account_name': 'Savings Deposits - Target',
                'account_type': liability_type,
                'account_category': savings_cat,
                'description': 'Target savings deposits from clients',
                'is_control_account': False,
                'allows_manual_entries': False,
            },
            {
                'gl_code': '2040',
                'account_name': 'Savings Deposits - Children',
                'account_type': liability_type,
                'account_category': savings_cat,
                'description': 'Children savings deposits',
                'is_control_account': False,
                'allows_manual_entries': False,
            },

            # Interest Payable (2100-2199)
            {
                'gl_code': '2110',
                'account_name': 'Interest Payable - Savings',
                'account_type': liability_type,
                'account_category': interest_payable_cat,
                'description': 'Accrued interest payable on savings deposits',
                'is_control_account': False,
                'allows_manual_entries': False,
            },

            # Other Liabilities (2900-2999)
            {
                'gl_code': '2910',
                'account_name': 'Accounts Payable',
                'account_type': liability_type,
                'account_category': liability_other_cat,
                'description': 'Outstanding bills and invoices',
                'is_control_account': False,
                'allows_manual_entries': True,
            },
            {
                'gl_code': '2920',
                'account_name': 'Accrued Expenses',
                'account_type': liability_type,
                'account_category': liability_other_cat,
                'description': 'Expenses incurred but not yet paid',
                'is_control_account': False,
                'allows_manual_entries': True,
            },

            # ====================================================================
            # EQUITY
            # ====================================================================

            # Capital (3000-3099)
            {
                'gl_code': '3010',
                'account_name': 'Share Capital',
                'account_type': equity_type,
                'account_category': capital_cat,
                'description': 'Initial and additional capital invested',
                'is_control_account': False,
                'allows_manual_entries': True,
            },
            {
                'gl_code': '3020',
                'account_name': 'Retained Earnings',
                'account_type': equity_type,
                'account_category': capital_cat,
                'description': 'Accumulated profits from prior years',
                'is_control_account': False,
                'allows_manual_entries': True,
            },

            # Current Year (3100-3199)
            {
                'gl_code': '3110',
                'account_name': 'Current Year Profit/Loss',
                'account_type': equity_type,
                'account_category': current_year_cat,
                'description': 'Net profit or loss for current financial year',
                'is_control_account': False,
                'allows_manual_entries': False,
            },

            # ====================================================================
            # INCOME
            # ====================================================================

            # Interest Income (4000-4099)
            {
                'gl_code': '4010',
                'account_name': 'Interest Income - Loans',
                'account_type': income_type,
                'account_category': interest_income_cat,
                'description': 'Interest earned on loans to clients',
                'is_control_account': False,
                'allows_manual_entries': False,
            },
            {
                'gl_code': '4020',
                'account_name': 'Interest Income - Investments',
                'account_type': income_type,
                'account_category': interest_income_cat,
                'description': 'Interest earned from bank deposits and investments',
                'is_control_account': False,
                'allows_manual_entries': True,
            },

            # Fee Income (4100-4199)
            {
                'gl_code': '4110',
                'account_name': 'Registration Fee Income',
                'account_type': income_type,
                'account_category': fee_income_cat,
                'description': 'Client registration fees',
                'is_control_account': False,
                'allows_manual_entries': False,
            },
            {
                'gl_code': '4120',
                'account_name': 'Loan Application Fee Income',
                'account_type': income_type,
                'account_category': fee_income_cat,
                'description': 'Loan form and application fees',
                'is_control_account': False,
                'allows_manual_entries': False,
            },
            {
                'gl_code': '4130',
                'account_name': 'Loan Insurance Fee Income',
                'account_type': income_type,
                'account_category': fee_income_cat,
                'description': 'Insurance fees collected on loans',
                'is_control_account': False,
                'allows_manual_entries': False,
            },
            {
                'gl_code': '4140',
                'account_name': 'Processing Fee Income',
                'account_type': income_type,
                'account_category': fee_income_cat,
                'description': 'Loan processing fees',
                'is_control_account': False,
                'allows_manual_entries': False,
            },
            {
                'gl_code': '4150',
                'account_name': 'Risk Premium Income',
                'account_type': income_type,
                'account_category': fee_income_cat,
                'description': 'Risk premium fees',
                'is_control_account': False,
                'allows_manual_entries': False,
            },
            {
                'gl_code': '4160',
                'account_name': 'Technology Fee Income',
                'account_type': income_type,
                'account_category': fee_income_cat,
                'description': 'Technology and platform fees',
                'is_control_account': False,
                'allows_manual_entries': False,
            },
            {
                'gl_code': '4170',
                'account_name': 'Late Payment Fee Income',
                'account_type': income_type,
                'account_category': fee_income_cat,
                'description': 'Penalty fees for late payments',
                'is_control_account': False,
                'allows_manual_entries': False,
            },

            # ====================================================================
            # EXPENSES
            # ====================================================================

            # Interest Expense (5000-5099)
            {
                'gl_code': '5010',
                'account_name': 'Interest Expense - Savings',
                'account_type': expense_type,
                'account_category': interest_expense_cat,
                'description': 'Interest paid to clients on savings deposits',
                'is_control_account': False,
                'allows_manual_entries': False,
            },

            # Operating Expenses (5100-5199)
            {
                'gl_code': '5110',
                'account_name': 'Salaries & Wages',
                'account_type': expense_type,
                'account_category': operating_expense_cat,
                'description': 'Staff salaries and wages',
                'is_control_account': False,
                'allows_manual_entries': True,
            },
            {
                'gl_code': '5120',
                'account_name': 'Rent Expense',
                'account_type': expense_type,
                'account_category': operating_expense_cat,
                'description': 'Office and branch rental costs',
                'is_control_account': False,
                'allows_manual_entries': True,
            },
            {
                'gl_code': '5130',
                'account_name': 'Utilities Expense',
                'account_type': expense_type,
                'account_category': operating_expense_cat,
                'description': 'Electricity, water, internet, phone',
                'is_control_account': False,
                'allows_manual_entries': True,
            },
            {
                'gl_code': '5140',
                'account_name': 'Office Supplies',
                'account_type': expense_type,
                'account_category': operating_expense_cat,
                'description': 'Stationery, printing, and office supplies',
                'is_control_account': False,
                'allows_manual_entries': True,
            },

            # Loan Loss Provisions (5900-5999)
            {
                'gl_code': '5910',
                'account_name': 'Provision for Bad Debts',
                'account_type': expense_type,
                'account_category': provision_cat,
                'description': 'Provision for uncollectible loans',
                'is_control_account': False,
                'allows_manual_entries': True,
            },
        ]

        for account_data in accounts:
            account, created = ChartOfAccounts.objects.get_or_create(
                gl_code=account_data['gl_code'],
                defaults={
                    'account_name': account_data['account_name'],
                    'account_type': account_data['account_type'],
                    'account_category': account_data['account_category'],
                    'description': account_data['description'],
                    'is_control_account': account_data['is_control_account'],
                    'allows_manual_entries': account_data['allows_manual_entries'],
                    'currency': 'NGN',
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f'  [+] Created: {account.gl_code} - {account.account_name}')
            else:
                self.stdout.write(f'  [*] Exists: {account.gl_code} - {account.account_name}')

        # Print summary
        self.stdout.write('\n--- Summary ---')
        self.stdout.write(f'Total Accounts: {ChartOfAccounts.objects.count()}')
        self.stdout.write(f'  Assets: {ChartOfAccounts.objects.filter(account_type__name=AccountType.ASSET).count()}')
        self.stdout.write(f'  Liabilities: {ChartOfAccounts.objects.filter(account_type__name=AccountType.LIABILITY).count()}')
        self.stdout.write(f'  Equity: {ChartOfAccounts.objects.filter(account_type__name=AccountType.EQUITY).count()}')
        self.stdout.write(f'  Income: {ChartOfAccounts.objects.filter(account_type__name=AccountType.INCOME).count()}')
        self.stdout.write(f'  Expenses: {ChartOfAccounts.objects.filter(account_type__name=AccountType.EXPENSE).count()}')
