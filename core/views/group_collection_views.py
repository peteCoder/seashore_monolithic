"""
Group Collection Views
=====================

Views for bulk collection of loan repayments and savings deposits within client groups.

Workflow:
1. Staff navigates to group → clicks "Collect Loan Repayments" or "Collect Savings"
2. Staff enters total amount collected and individual amounts per member
3. System validates: sum of individual amounts == total entered
4. Staff submits → creates GroupCollectionSession (pending approval)
5. Manager/Director/Admin approves → processes all individual payments
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from decimal import Decimal, InvalidOperation

from core.models import (
    ClientGroup, Client, Loan, SavingsAccount,
    GroupCollectionSession, GroupCollectionItem,
    GroupSavingsCollectionSession, GroupSavingsCollectionItem,
)
from core.permissions import PermissionChecker


def _check_group_permission(checker, group, request):
    """Check if user has permission to collect for this group"""
    if checker.is_staff():
        if group.loan_officer != request.user:
            raise PermissionDenied("You don't have permission to collect for this group")
    elif checker.is_manager():
        if group.branch != request.user.branch:
            raise PermissionDenied("You can only manage groups in your branch")


# =============================================================================
# GROUP COLLECTION LIST
# =============================================================================

@login_required
def group_collection_list(request):
    """List all client groups for collection management"""
    checker = PermissionChecker(request.user)

    groups = ClientGroup.objects.select_related(
        'branch', 'loan_officer'
    ).filter(status='active')

    if checker.is_staff():
        groups = groups.filter(loan_officer=request.user)
    elif checker.is_manager():
        groups = groups.filter(branch=request.user.branch)

    search = request.GET.get('search', '')
    if search:
        groups = groups.filter(
            Q(name__icontains=search) | Q(code__icontains=search)
        )

    groups = groups.order_by('meeting_day', 'name')

    paginator = Paginator(groups, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    summary = {
        'total_groups': groups.count(),
        'total_members': groups.aggregate(Sum('total_members'))['total_members__sum'] or 0,
        'total_outstanding': groups.aggregate(Sum('total_loans_outstanding'))['total_loans_outstanding__sum'] or Decimal('0.00'),
    }

    # Recent collection sessions
    recent_sessions = GroupCollectionSession.objects.select_related(
        'group', 'collected_by'
    ).order_by('-created_at')[:10]

    if checker.is_staff():
        recent_sessions = recent_sessions.filter(collected_by=request.user)
    elif checker.is_manager():
        recent_sessions = recent_sessions.filter(group__branch=request.user.branch)

    context = {
        'page_title': 'Group Collections',
        'groups': page_obj,
        'summary': summary,
        'search': search,
        'recent_sessions': recent_sessions,
        'checker': checker,
    }

    return render(request, 'groups/collection_list.html', context)


# =============================================================================
# LOAN COLLECTION - COLLECT
# =============================================================================

@login_required
def group_collection_detail(request, group_id):
    """Show group members with active loans for collection"""
    group = get_object_or_404(
        ClientGroup.objects.select_related('branch', 'loan_officer'),
        id=group_id
    )
    checker = PermissionChecker(request.user)
    _check_group_permission(checker, group, request)

    members_with_loans = Client.objects.filter(
        client_group=group,
        is_active=True,
        loans__status__in=['active', 'overdue']
    ).select_related('branch').prefetch_related('loans').distinct()

    member_loan_data = []
    for member in members_with_loans:
        active_loans = member.loans.filter(status__in=['active', 'overdue'])
        for loan in active_loans:
            member_loan_data.append({
                'client': member,
                'loan': loan,
            })

    total_outstanding = sum([d['loan'].outstanding_balance for d in member_loan_data])

    # Recent sessions for this group
    recent_sessions = GroupCollectionSession.objects.filter(
        group=group
    ).select_related('collected_by', 'approved_by').order_by('-created_at')[:5]

    context = {
        'page_title': f'Collect Loan Repayments - {group.name}',
        'group': group,
        'member_loan_data': member_loan_data,
        'total_outstanding': total_outstanding,
        'recent_sessions': recent_sessions,
        'checker': checker,
        'today': timezone.now().date().isoformat(),
    }

    return render(request, 'groups/collection_detail.html', context)


@login_required
@transaction.atomic
def group_collection_post(request, group_id):
    """Process loan repayment collection - creates a GroupCollectionSession"""
    group = get_object_or_404(ClientGroup, id=group_id)
    checker = PermissionChecker(request.user)
    _check_group_permission(checker, group, request)

    if request.method != 'POST':
        return redirect('core:group_collection_detail', group_id=group.id)

    total_amount_entered = request.POST.get('total_amount', '0')
    payment_method = request.POST.get('payment_method', 'cash')
    payment_date = request.POST.get('payment_date')
    payment_reference = request.POST.get('payment_reference', '')
    notes = request.POST.get('notes', '')

    try:
        total_amount_entered = Decimal(total_amount_entered)
    except (InvalidOperation, ValueError):
        messages.error(request, 'Invalid total amount entered.')
        return redirect('core:group_collection_detail', group_id=group.id)

    if total_amount_entered <= 0:
        messages.error(request, 'Total amount must be greater than zero.')
        return redirect('core:group_collection_detail', group_id=group.id)

    # Collect individual amounts
    items_data = []
    cumulative_total = Decimal('0.00')

    for key, value in request.POST.items():
        if key.startswith('amount_') and value:
            loan_id = key.replace('amount_', '')
            try:
                amount = Decimal(value)
                if amount > 0:
                    loan = Loan.objects.get(id=loan_id, client__client_group=group)
                    if amount > loan.outstanding_balance:
                        messages.error(
                            request,
                            f'{loan.client.get_full_name()} ({loan.loan_number}): '
                            f'Amount ₦{amount:,.2f} exceeds outstanding balance ₦{loan.outstanding_balance:,.2f}'
                        )
                        return redirect('core:group_collection_detail', group_id=group.id)
                    items_data.append({'loan': loan, 'amount': amount})
                    cumulative_total += amount
            except (Loan.DoesNotExist, InvalidOperation, ValueError):
                continue

    if not items_data:
        messages.error(request, 'No valid amounts were entered for any member.')
        return redirect('core:group_collection_detail', group_id=group.id)

    # Validate total matches cumulative
    if abs(total_amount_entered - cumulative_total) > Decimal('0.01'):
        messages.error(
            request,
            f'Total amount entered (₦{total_amount_entered:,.2f}) does not match '
            f'the sum of individual amounts (₦{cumulative_total:,.2f}). '
            f'Please correct and try again.'
        )
        return redirect('core:group_collection_detail', group_id=group.id)

    # Create the session
    session = GroupCollectionSession.objects.create(
        group=group,
        collected_by=request.user,
        collection_date=payment_date,
        total_amount=total_amount_entered,
        status='pending',
        notes=notes or f'Loan collection via {payment_method}. Ref: {payment_reference}',
    )

    # Create individual items
    for item_data in items_data:
        GroupCollectionItem.objects.create(
            session=session,
            loan=item_data['loan'],
            amount=item_data['amount'],
            notes=f'Group collection - {payment_method}',
        )

    messages.success(
        request,
        f'Collection session created with {len(items_data)} payment(s) totalling ₦{total_amount_entered:,.2f}. '
        f'Awaiting approval from a manager or director.'
    )
    return redirect('core:group_collection_session_detail', session_id=session.id)


# =============================================================================
# SAVINGS COLLECTION - COLLECT
# =============================================================================

@login_required
def group_savings_collection(request, group_id):
    """Show group members with savings accounts for collection"""
    group = get_object_or_404(
        ClientGroup.objects.select_related('branch', 'loan_officer'),
        id=group_id
    )
    checker = PermissionChecker(request.user)
    _check_group_permission(checker, group, request)

    members_with_savings = Client.objects.filter(
        client_group=group,
        is_active=True,
        savings_accounts__status='active'
    ).select_related('branch').prefetch_related('savings_accounts').distinct()

    member_savings_data = []
    for member in members_with_savings:
        active_accounts = member.savings_accounts.filter(status='active')
        for account in active_accounts:
            member_savings_data.append({
                'client': member,
                'account': account,
            })

    total_savings = sum([d['account'].balance for d in member_savings_data])

    recent_sessions = GroupSavingsCollectionSession.objects.filter(
        group=group
    ).select_related('collected_by', 'approved_by').order_by('-created_at')[:5]

    context = {
        'page_title': f'Collect Savings - {group.name}',
        'group': group,
        'member_savings_data': member_savings_data,
        'total_savings': total_savings,
        'recent_sessions': recent_sessions,
        'checker': checker,
        'today': timezone.now().date().isoformat(),
    }

    return render(request, 'groups/savings_collection.html', context)


@login_required
@transaction.atomic
def group_savings_collection_post(request, group_id):
    """Process savings deposit collection"""
    group = get_object_or_404(ClientGroup, id=group_id)
    checker = PermissionChecker(request.user)
    _check_group_permission(checker, group, request)

    if request.method != 'POST':
        return redirect('core:group_savings_collection', group_id=group.id)

    total_amount_entered = request.POST.get('total_amount', '0')
    payment_date = request.POST.get('payment_date')
    notes = request.POST.get('notes', '')

    try:
        total_amount_entered = Decimal(total_amount_entered)
    except (InvalidOperation, ValueError):
        messages.error(request, 'Invalid total amount entered.')
        return redirect('core:group_savings_collection', group_id=group.id)

    if total_amount_entered <= 0:
        messages.error(request, 'Total amount must be greater than zero.')
        return redirect('core:group_savings_collection', group_id=group.id)

    items_data = []
    cumulative_total = Decimal('0.00')

    for key, value in request.POST.items():
        if key.startswith('amount_') and value:
            account_id = key.replace('amount_', '')
            try:
                amount = Decimal(value)
                if amount > 0:
                    account = SavingsAccount.objects.get(
                        id=account_id, client__client_group=group, status='active'
                    )
                    client = account.client
                    items_data.append({'client': client, 'account': account, 'amount': amount})
                    cumulative_total += amount
            except (SavingsAccount.DoesNotExist, InvalidOperation, ValueError):
                continue

    if not items_data:
        messages.error(request, 'No valid amounts were entered for any member.')
        return redirect('core:group_savings_collection', group_id=group.id)

    if abs(total_amount_entered - cumulative_total) > Decimal('0.01'):
        messages.error(
            request,
            f'Total amount entered (₦{total_amount_entered:,.2f}) does not match '
            f'the sum of individual amounts (₦{cumulative_total:,.2f}). '
            f'Please correct and try again.'
        )
        return redirect('core:group_savings_collection', group_id=group.id)

    session = GroupSavingsCollectionSession.objects.create(
        group=group,
        collected_by=request.user,
        collection_date=payment_date,
        total_amount=total_amount_entered,
        status='pending',
        notes=notes or 'Savings collection',
    )

    for item_data in items_data:
        GroupSavingsCollectionItem.objects.create(
            session=session,
            client=item_data['client'],
            savings_account=item_data['account'],
            amount=item_data['amount'],
        )

    messages.success(
        request,
        f'Savings collection created with {len(items_data)} deposit(s) totalling ₦{total_amount_entered:,.2f}. '
        f'Awaiting approval.'
    )
    return redirect('core:group_savings_session_detail', session_id=session.id)


# =============================================================================
# SESSION DETAIL VIEWS
# =============================================================================

@login_required
def group_collection_session_detail(request, session_id):
    """View a loan collection session"""
    session = get_object_or_404(
        GroupCollectionSession.objects.select_related(
            'group', 'collected_by', 'approved_by', 'rejected_by'
        ),
        id=session_id
    )
    items = session.items.select_related('loan', 'loan__client').order_by('created_at')

    context = {
        'page_title': f'Loan Collection - {session.group.name}',
        'session': session,
        'items': items,
        'checker': PermissionChecker(request.user),
    }
    return render(request, 'groups/collection_session_detail.html', context)


@login_required
def group_savings_session_detail(request, session_id):
    """View a savings collection session"""
    session = get_object_or_404(
        GroupSavingsCollectionSession.objects.select_related(
            'group', 'collected_by', 'approved_by', 'rejected_by'
        ),
        id=session_id
    )
    items = session.items.select_related('client', 'savings_account').order_by('created_at')

    context = {
        'page_title': f'Savings Collection - {session.group.name}',
        'session': session,
        'items': items,
        'checker': PermissionChecker(request.user),
    }
    return render(request, 'groups/savings_session_detail.html', context)


# =============================================================================
# APPROVAL VIEWS
# =============================================================================

@login_required
@transaction.atomic
def group_collection_approve(request, session_id):
    """Approve or reject a loan collection session"""
    session = get_object_or_404(
        GroupCollectionSession.objects.select_related('group', 'collected_by'),
        id=session_id
    )
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_admin_or_director()):
        raise PermissionDenied("Only managers, directors or admins can approve collections")

    if session.status != 'pending':
        messages.warning(request, 'This collection has already been processed.')
        return redirect('core:group_collection_session_detail', session_id=session.id)

    if request.method == 'POST':
        decision = request.POST.get('decision')
        review_notes = request.POST.get('notes', '')

        if decision == 'approve':
            items = session.items.select_related('loan', 'loan__client')
            errors = []

            for item in items:
                try:
                    if item.loan.status not in ['active', 'overdue']:
                        errors.append(f'{item.loan.loan_number}: Loan is {item.loan.get_status_display()}')
                        continue
                    if item.amount > item.loan.outstanding_balance:
                        errors.append(f'{item.loan.loan_number}: Amount exceeds balance')
                        continue

                    item.loan.record_repayment(
                        amount=item.amount,
                        processed_by=request.user,
                        description=f'Group collection: {session.group.name} ({session.collection_date})'
                    )
                except Exception as e:
                    errors.append(f'{item.loan.loan_number}: {str(e)}')

            if errors:
                for error in errors:
                    messages.warning(request, error)

            session.status = 'approved'
            session.approved_by = request.user
            session.approved_at = timezone.now()
            session.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

            success_count = items.count() - len(errors)
            messages.success(
                request,
                f'Collection approved! {success_count} loan repayment(s) processed successfully.'
            )

        elif decision == 'reject':
            if not review_notes:
                messages.error(request, 'Please provide a reason for rejection.')
                return redirect('core:group_collection_approve', session_id=session.id)

            session.status = 'rejected'
            session.rejected_by = request.user
            session.rejected_at = timezone.now()
            session.rejection_reason = review_notes
            session.save(update_fields=[
                'status', 'rejected_by', 'rejected_at', 'rejection_reason', 'updated_at'
            ])
            messages.success(request, 'Collection session rejected.')

        return redirect('core:group_collection_session_detail', session_id=session.id)

    items = session.items.select_related('loan', 'loan__client')

    context = {
        'page_title': f'Approve Collection - {session.group.name}',
        'session': session,
        'items': items,
        'checker': checker,
    }
    return render(request, 'groups/collection_approve.html', context)


@login_required
@transaction.atomic
def group_savings_collection_approve(request, session_id):
    """Approve or reject a savings collection session"""
    session = get_object_or_404(
        GroupSavingsCollectionSession.objects.select_related('group', 'collected_by'),
        id=session_id
    )
    checker = PermissionChecker(request.user)

    if not (checker.is_manager() or checker.is_admin_or_director()):
        raise PermissionDenied("Only managers, directors or admins can approve collections")

    if session.status != 'pending':
        messages.warning(request, 'This collection has already been processed.')
        return redirect('core:group_savings_session_detail', session_id=session.id)

    if request.method == 'POST':
        decision = request.POST.get('decision')
        review_notes = request.POST.get('notes', '')

        if decision == 'approve':
            items = session.items.select_related('savings_account', 'client')
            errors = []

            for item in items:
                try:
                    item.savings_account.deposit(
                        amount=item.amount,
                        processed_by=request.user,
                        description=f'Group savings collection: {session.group.name} ({session.collection_date})'
                    )
                except Exception as e:
                    errors.append(f'{item.client.get_full_name()}: {str(e)}')

            if errors:
                for error in errors:
                    messages.warning(request, error)

            session.status = 'approved'
            session.approved_by = request.user
            session.approved_at = timezone.now()
            session.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

            success_count = items.count() - len(errors)
            messages.success(
                request,
                f'Savings collection approved! {success_count} deposit(s) processed successfully.'
            )

        elif decision == 'reject':
            if not review_notes:
                messages.error(request, 'Please provide a reason for rejection.')
                return redirect('core:group_savings_collection_approve', session_id=session.id)

            session.status = 'rejected'
            session.rejected_by = request.user
            session.rejected_at = timezone.now()
            session.rejection_reason = review_notes
            session.save(update_fields=[
                'status', 'rejected_by', 'rejected_at', 'rejection_reason', 'updated_at'
            ])
            messages.success(request, 'Savings collection session rejected.')

        return redirect('core:group_savings_session_detail', session_id=session.id)

    items = session.items.select_related('savings_account', 'client')

    context = {
        'page_title': f'Approve Savings Collection - {session.group.name}',
        'session': session,
        'items': items,
        'checker': checker,
    }
    return render(request, 'groups/savings_collection_approve.html', context)
