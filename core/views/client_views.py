"""
Client Views
============

All client CRUD operations with role-based permissions
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from decimal import Decimal

from core.models import Client, Transaction, CLIENT_REGISTRATION_FEE
from core.forms.client_forms import (
    ClientCreateForm,
    ClientUpdateForm,
    ClientSearchForm,
    ClientApprovalForm,
    AssignStaffForm,
    RegistrationFeePaymentForm,
)
from core.permissions import PermissionChecker


# =============================================================================
# CLIENT LIST VIEW
# =============================================================================

@login_required
def client_list(request):
    """
    Display paginated list of clients with search and filters

    Permissions: All authenticated users (role-filtered)
    - Admin/Director: See all clients
    - Manager: See branch clients only
    - Staff: See assigned clients only
    """
    checker = PermissionChecker(request.user)

    # Base queryset (role-filtered)
    clients = checker.filter_clients(Client.objects.all())

    # Search form
    search_form = ClientSearchForm(request.GET or None)

    # Apply filters
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        if search:
            clients = clients.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(client_id__icontains=search)
            )

        branch = search_form.cleaned_data.get('branch')
        if branch:
            clients = clients.filter(branch=branch)

        status = search_form.cleaned_data.get('status')
        if status == 'active':
            clients = clients.filter(is_active=True)
        elif status == 'inactive':
            clients = clients.filter(is_active=False)

        approval_status = search_form.cleaned_data.get('approval_status')
        if approval_status:
            clients = clients.filter(approval_status=approval_status)

        level = search_form.cleaned_data.get('level')
        if level:
            clients = clients.filter(level=level)

    # Prefetch related data for performance
    clients = clients.select_related('branch', 'group', 'assigned_staff').order_by('-created_at')

    # Pagination (25 per page)
    paginator = Paginator(clients, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Context
    context = {
        'page_title': 'Clients',
        'clients': page_obj,
        'search_form': search_form,
        'checker': checker,
        'total_count': clients.count(),
    }

    return render(request, 'clients/list.html', context)


# =============================================================================
# CLIENT DETAIL VIEW
# =============================================================================

@login_required
def client_detail(request, client_id):
    """
    Display comprehensive client information with related data

    Shows:
    - All client information
    - Active loans with repayment status
    - Savings accounts with balances
    - Recent transactions
    - Group membership
    - Assigned staff
    - Action buttons based on permissions
    """
    checker = PermissionChecker(request.user)

    # Get client with related data
    client = get_object_or_404(
        Client.objects.select_related('branch', 'group', 'assigned_staff', 'original_officer'),
        id=client_id
    )

    # Permission check
    if not checker.can_view_client(client):
        messages.error(request, 'You do not have permission to view this client.')
        raise PermissionDenied

    # Get related data
    loans = client.loans.all().order_by('-created_at')[:10]
    savings_accounts = client.savings_accounts.all().select_related('savings_product')
    recent_transactions = client.transactions.all().order_by('-transaction_date')[:15]

    # Calculate financial summary
    total_loans = client.loans.filter(status__in=['active', 'disbursed', 'overdue']).aggregate(
        total=Sum('principal_amount'),
        outstanding=Sum('outstanding_balance')
    )

    total_savings = savings_accounts.filter(status='active').aggregate(
        total=Sum('balance')
    )

    # Context
    context = {
        'page_title': f'Client: {client.get_full_name()}',
        'client': client,
        'loans': loans,
        'savings_accounts': savings_accounts,
        'recent_transactions': recent_transactions,
        'total_loans': total_loans['total'] or Decimal('0.00'),
        'total_outstanding': total_loans['outstanding'] or Decimal('0.00'),
        'total_savings': total_savings['total'] or Decimal('0.00'),
        'checker': checker,
    }

    return render(request, 'clients/detail.html', context)


# =============================================================================
# CLIENT CREATE VIEW
# =============================================================================

@login_required
def client_create(request):
    """
    Create new client with multi-tab form

    5 Tabs:
    1. Personal Information
    2. Contact & Address
    3. Identification & Documents
    4. Employment & Business
    5. Banking & Emergency Contact

    Permissions: Staff, Manager, Director, Admin
    """
    checker = PermissionChecker(request.user)

    # Permission check
    if not checker.can_create_client():
        messages.error(request, 'You do not have permission to create clients.')
        raise PermissionDenied

    if request.method == 'POST':
        form = ClientCreateForm(request.POST, request.FILES, user=request.user)

        if form.is_valid():
            client = form.save(commit=False)

            # Set defaults
            client.approval_status = 'draft'
            client.is_active = False

            # Set assigned staff
            if request.user.user_role == 'staff':
                client.assigned_staff = request.user
                client.original_officer = request.user

            client.save()

            messages.success(
                request,
                f'Client {client.get_full_name()} created successfully! Client ID: {client.client_id}'
            )
            return redirect('core:client_detail', client_id=client.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientCreateForm(user=request.user)

    context = {
        'page_title': 'Register New Client',
        'form': form,
        'is_create': True,
    }

    return render(request, 'clients/form.html', context)


# =============================================================================
# CLIENT UPDATE VIEW
# =============================================================================

@login_required
def client_update(request, client_id):
    """
    Update existing client information

    Uses same multi-tab form as create

    Permissions: Manager, Director, Admin (not Staff)
    - Manager: Can edit clients in their branch only
    - Director/Admin: Can edit any client
    """
    checker = PermissionChecker(request.user)

    client = get_object_or_404(Client, id=client_id)

    # Permission check
    if not checker.can_edit_client(client):
        messages.error(request, 'You do not have permission to edit this client.')
        raise PermissionDenied

    if request.method == 'POST':
        form = ClientUpdateForm(request.POST, request.FILES, instance=client, user=request.user)

        if form.is_valid():
            client = form.save()
            messages.success(request, f'Client {client.get_full_name()} updated successfully!')
            return redirect('core:client_detail', client_id=client.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ClientUpdateForm(instance=client, user=request.user)

    context = {
        'page_title': f'Edit Client: {client.get_full_name()}',
        'form': form,
        'client': client,
        'is_create': False,
    }

    return render(request, 'clients/form.html', context)


# =============================================================================
# CLIENT APPROVE VIEW
# =============================================================================

@login_required
def client_approve(request, client_id):
    """
    Approve or reject client application

    Permissions: Manager, Director, Admin
    """
    checker = PermissionChecker(request.user)

    if not checker.can_approve_client():
        messages.error(request, 'You do not have permission to approve clients.')
        raise PermissionDenied

    client = get_object_or_404(Client, id=client_id)

    # Can only approve draft or pending clients
    if client.approval_status not in ['draft', 'pending']:
        messages.error(request, 'This client cannot be approved. Only draft or pending clients can be approved.')
        return redirect('core:client_detail', client_id=client.id)

    if request.method == 'POST':
        form = ClientApprovalForm(request.POST)

        if form.is_valid():
            action = form.cleaned_data['action']
            notes = form.cleaned_data.get('notes', '')

            if action == 'approve':
                client.approval_status = 'approved'
                client.approved_by = request.user
                client.approved_at = timezone.now()
                client.save()

                messages.success(request, f'Client {client.get_full_name()} approved successfully!')
            else:  # reject
                client.approval_status = 'rejected'
                client.approved_by = request.user
                client.approved_at = timezone.now()
                client.notes = notes  # Store rejection reason
                client.save()

                messages.warning(request, f'Client {client.get_full_name()} rejected.')

            return redirect('core:client_detail', client_id=client.id)
    else:
        form = ClientApprovalForm()

    context = {
        'page_title': f'Approve Client: {client.get_full_name()}',
        'client': client,
        'form': form,
    }

    return render(request, 'clients/approve.html', context)


# =============================================================================
# CLIENT ACTIVATE VIEW
# =============================================================================

@login_required
def client_activate(request, client_id):
    """
    Activate inactive client

    Permissions: Manager, Director, Admin

    Requirements:
    - Client must be approved
    - Client must be inactive
    - Registration fee must be paid
    """
    checker = PermissionChecker(request.user)

    if not checker.can_activate_client():
        messages.error(request, 'You do not have permission to activate clients.')
        raise PermissionDenied

    client = get_object_or_404(Client, id=client_id)

    # Validation
    if client.is_active:
        messages.warning(request, 'This client is already active.')
        return redirect('core:client_detail', client_id=client.id)

    if client.approval_status != 'approved':
        messages.error(request, 'Client must be approved before activation.')
        return redirect('core:client_detail', client_id=client.id)

    if not client.registration_fee_paid:
        messages.error(request, 'Registration fee must be paid before activation.')
        return redirect('core:client_detail', client_id=client.id)

    if request.method == 'POST':
        client.is_active = True
        client.save()

        messages.success(request, f'Client {client.get_full_name()} activated successfully!')
        return redirect('core:client_detail', client_id=client.id)

    context = {
        'page_title': f'Activate Client: {client.get_full_name()}',
        'client': client,
    }

    return render(request, 'clients/activate_confirm.html', context)


# =============================================================================
# CLIENT DEACTIVATE VIEW
# =============================================================================

@login_required
def client_deactivate(request, client_id):
    """
    Deactivate active client

    Permissions: Manager, Director, Admin

    Checks:
    - Cannot deactivate if active loans exist
    """
    checker = PermissionChecker(request.user)

    if not checker.can_deactivate_client():
        messages.error(request, 'You do not have permission to deactivate clients.')
        raise PermissionDenied

    client = get_object_or_404(Client, id=client_id)

    if not client.is_active:
        messages.warning(request, 'This client is already inactive.')
        return redirect('core:client_detail', client_id=client.id)

    # Check for active loans
    active_loans = client.loans.filter(status__in=['active', 'disbursed', 'overdue']).count()
    if active_loans > 0:
        messages.error(
            request,
            f'Cannot deactivate client with {active_loans} active loan(s). Please close all loans first.'
        )
        return redirect('core:client_detail', client_id=client.id)

    if request.method == 'POST':
        reason = request.POST.get('reason', '')

        client.is_active = False
        client.notes = f"{client.notes}\n\nDeactivated: {reason}" if client.notes else f"Deactivated: {reason}"
        client.save()

        messages.success(request, f'Client {client.get_full_name()} deactivated successfully.')
        return redirect('core:client_detail', client_id=client.id)

    context = {
        'page_title': f'Deactivate Client: {client.get_full_name()}',
        'client': client,
    }

    return render(request, 'clients/deactivate_confirm.html', context)


# =============================================================================
# CLIENT DELETE VIEW
# =============================================================================

@login_required
def client_delete(request, client_id):
    """
    Soft delete client (admin only)

    Permissions: Admin only

    Requirements:
    - No active loans
    - No savings balance
    """
    checker = PermissionChecker(request.user)

    if not checker.can_delete_client():
        messages.error(request, 'You do not have permission to delete clients.')
        raise PermissionDenied

    client = get_object_or_404(Client, id=client_id)

    # Validation
    active_loans = client.loans.filter(status__in=['active', 'disbursed', 'overdue']).count()
    if active_loans > 0:
        messages.error(request, f'Cannot delete client with {active_loans} active loan(s).')
        return redirect('core:client_detail', client_id=client.id)

    total_savings = client.savings_accounts.filter(status='active').aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')

    if total_savings > 0:
        messages.error(
            request,
            f'Cannot delete client with savings balance of ₦{total_savings:,.2f}. Please withdraw all funds first.'
        )
        return redirect('core:client_detail', client_id=client.id)

    if request.method == 'POST':
        client_name = client.get_full_name()
        client.delete()  # Soft delete (sets deleted_at)

        messages.success(request, f'Client {client_name} deleted successfully.')
        return redirect('core:client_list')

    context = {
        'page_title': f'Delete Client: {client.get_full_name()}',
        'client': client,
    }

    return render(request, 'clients/delete_confirm.html', context)


@login_required
def client_assign_staff(request, client_id):
    """
    Assign staff to a client

    Permissions: Manager, Director, Admin

    Requirements:
    - Staff must be from the same branch as the client
    """
    checker = PermissionChecker(request.user)

    # Check permissions - only managers, directors, and admins
    if not (checker.is_admin_or_director() or checker.is_manager()):
        messages.error(request, 'You do not have permission to assign staff to clients.')
        raise PermissionDenied

    client = get_object_or_404(Client, id=client_id)

    # Branch check for managers
    if checker.is_manager() and client.branch != request.user.branch:
        messages.error(request, 'You can only assign staff to clients in your branch.')
        raise PermissionDenied

    if request.method == 'POST':
        form = AssignStaffForm(request.POST, branch=client.branch)

        if form.is_valid():
            staff = form.cleaned_data['staff']
            notes = form.cleaned_data.get('notes', '')

            # Update client's assigned staff
            old_staff = client.assigned_staff
            client.assigned_staff = staff
            client.save()

            # Create notification or log entry (optional)
            if old_staff:
                messages.success(
                    request,
                    f'Client {client.get_full_name()} reassigned from {old_staff.get_full_name()} to {staff.get_full_name()}.'
                )
            else:
                messages.success(
                    request,
                    f'Staff {staff.get_full_name()} assigned to client {client.get_full_name()}.'
                )

            return redirect('core:client_detail', client_id=client.id)
    else:
        form = AssignStaffForm(branch=client.branch)

    context = {
        'page_title': f'Assign Staff: {client.get_full_name()}',
        'client': client,
        'form': form,
    }

    return render(request, 'clients/assign_staff.html', context)


# =============================================================================
# REGISTRATION FEE PAYMENT VIEW
# =============================================================================

@login_required
def client_pay_registration_fee(request, client_id):
    """
    Process registration fee payment for a client

    Permissions: All authenticated users (staff, manager, director, admin)
    This is a one-on-one interaction with the client
    """
    client = get_object_or_404(Client, id=client_id)

    # Check if registration fee is already paid
    if client.registration_fee_paid:
        messages.warning(request, 'Registration fee has already been paid for this client.')
        return redirect('core:client_detail', client_id=client.id)

    if request.method == 'POST':
        form = RegistrationFeePaymentForm(request.POST)

        if form.is_valid():
            payment_method = form.cleaned_data['payment_method']
            reference_number = form.cleaned_data.get('reference_number', '')
            notes = form.cleaned_data.get('notes', '')

            # Build payment details string
            payment_details = f"{payment_method.replace('_', ' ').title()}"
            if reference_number:
                payment_details += f" - Ref: {reference_number}"

            # Create transaction record
            transaction = Transaction.objects.create(
                client=client,
                branch=client.branch,
                transaction_type='registration_fee',
                amount=CLIENT_REGISTRATION_FEE,
                payment_details=payment_details,
                description=f"Client registration fee payment via {payment_method.replace('_', ' ')}",
                notes=notes,
                processed_by=request.user,
                status='completed',
                is_income=True
            )

            # Mark registration fee as paid
            client.registration_fee_paid = True
            client.save()

            messages.success(
                request,
                f'Registration fee of ₦{CLIENT_REGISTRATION_FEE:,.2f} recorded successfully for {client.get_full_name()}!'
            )

            return redirect('core:client_detail', client_id=client.id)
    else:
        form = RegistrationFeePaymentForm()

    context = {
        'page_title': f'Pay Registration Fee: {client.get_full_name()}',
        'client': client,
        'form': form,
        'registration_fee': CLIENT_REGISTRATION_FEE,
    }

    return render(request, 'clients/pay_registration_fee.html', context)
