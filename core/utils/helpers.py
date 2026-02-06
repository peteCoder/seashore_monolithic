from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from dateutil.relativedelta import relativedelta




# =============================================================================
# HELPER FUNCTION: GENERATE REPAYMENT SCHEDULE
# =============================================================================

def generate_repayment_schedule(loan):
    """
    Generate repayment schedule for a loan with status indicators
    
    Returns:
        list: Schedule with installment details and status
    """
    if not loan.disbursement_date and loan.status != 'approved':
        return []
    
    schedule = []
    
    # Calculate number of installments based on frequency
    frequency_multipliers = {
        'daily': 30,
        'weekly': 4,
        'fortnightly': 2,
        'monthly': 1
    }
    
    multiplier = frequency_multipliers.get(loan.repayment_frequency, 1)
    num_installments = loan.duration_months * multiplier
    
    # Calculate installment amounts
    installment_amount = loan.installment_amount
    total_amount = loan.total_repayment
    
    # For flat interest, split evenly
    interest_per_installment = loan.total_interest / num_installments
    principal_per_installment = loan.principal_amount / num_installments
    
    remaining_balance = total_amount
    
    # Start date
    if loan.disbursement_date:
        current_date = loan.first_repayment_date or loan.disbursement_date.date()
    else:
        # For approved loans (not yet disbursed)
        current_date = timezone.now().date() + timedelta(days=7)
    
    # Days between payments
    if loan.repayment_frequency == 'daily':
        days_between = 1
    elif loan.repayment_frequency == 'weekly':
        days_between = 7
    elif loan.repayment_frequency == 'fortnightly':
        days_between = 14
    else:  # monthly
        days_between = 30
    
    today = timezone.now().date()
    
    # Generate schedule
    for i in range(num_installments):
        installment_number = i + 1
        
        # Calculate due date
        if loan.repayment_frequency == 'monthly':
            due_date = current_date + relativedelta(months=i)
        else:
            due_date = current_date + timedelta(days=days_between * i)
        
        # Determine status
        is_paid = False
        is_overdue = False
        is_upcoming = False
        days_until = None
        days_overdue = None
        
        # Check if paid (simple calculation based on amount paid vs installment number)
        total_installments_paid = int(loan.amount_paid / installment_amount) if installment_amount > 0 else 0
        
        if installment_number <= total_installments_paid:
            is_paid = True
        elif due_date < today:
            is_overdue = True
            days_overdue = (today - due_date).days
        elif (due_date - today).days <= 7:
            is_upcoming = True
            days_until = (due_date - today).days
        
        # Adjust last installment for rounding
        if installment_number == num_installments:
            current_installment = remaining_balance
        else:
            current_installment = installment_amount
        
        remaining_balance -= current_installment
        
        # Determine status string
        if is_paid:
            status = 'paid'
        elif is_overdue:
            status = 'overdue'
        else:
            status = 'pending'

        schedule.append({
            'installment_number': installment_number,
            'due_date': due_date,
            'principal_amount': principal_per_installment,
            'interest_amount': interest_per_installment,
            'installment_amount': current_installment,
            'total_amount': current_installment,  # Alias for template compatibility
            'remaining_balance': max(remaining_balance, Decimal('0')),
            'status': status,
            'is_paid': is_paid,
            'is_overdue': is_overdue,
            'is_upcoming': is_upcoming,
            'days_until': days_until,
            'days_overdue': days_overdue,
        })
    
    return schedule


