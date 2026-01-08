from functools import wraps
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from supplies.models import Supply
from .models import SupplyRequest, SupplyRequestItem


LOW_STOCK_THRESHOLD = 2


def staff_required(view_func):
	@wraps(view_func)
	def _wrapped(request, *args, **kwargs):
		if not request.user.is_staff:
			messages.error(request, 'Staff access required.')
			return redirect('home')
		return view_func(request, *args, **kwargs)

	return login_required(_wrapped)


@login_required
def request_create(request):
	query = ''
	selected_from_session = request.session.get('selected_supplies')
	preselected = {}
	if selected_from_session:
		preselected = {int(item['supply_id']): item['quantity'] for item in selected_from_session if 'supply_id' in item and 'quantity' in item}
	supplies_qs = Supply.objects.filter(id__in=preselected.keys()) if preselected else Supply.objects.none()
	supplies = list(supplies_qs.order_by('name'))
	for s in supplies:
		s.prefill_qty = preselected.get(s.id)

	if request.method == 'POST':
		if not supplies:
			messages.info(request, 'Select supplies first.')
			return redirect('request_select_supplies')
		context = {'supplies': supplies, 'query': query, 'preselected': preselected}
		notes = request.POST.get('notes', '').strip()
		requester_name = request.POST.get('requester_name', '').strip()
		organization_name = request.POST.get('organization_name', '').strip()
		office_section = request.POST.get('office_section', '').strip()
		if not requester_name:
			messages.error(request, 'Full name is required.')
			context.update({'notes': notes, 'requester_name': requester_name, 'organization_name': organization_name, 'office_section': office_section})
			return render(request, 'requisitions/request_form.html', context)
		if not organization_name:
			messages.error(request, 'ID is required.')
			context.update({'notes': notes, 'requester_name': requester_name, 'organization_name': organization_name, 'office_section': office_section})
			return render(request, 'requisitions/request_form.html', context)
		if not office_section:
			messages.error(request, 'Office Section is required.')
			context.update({'notes': notes, 'requester_name': requester_name, 'organization_name': organization_name, 'office_section': office_section})
			return render(request, 'requisitions/request_form.html', context)
		context.update({'notes': notes, 'requester_name': requester_name, 'organization_name': organization_name, 'office_section': office_section})

		selections = []
		for supply in supplies:
			qty_str = request.POST.get(f'quantity_{supply.id}', '').strip()
			if not qty_str:
				messages.error(request, f'Quantity required for {supply.name}.')
				return render(request, 'requisitions/request_form.html', context)
			try:
				qty = int(qty_str)
			except ValueError:
				messages.error(request, f'Invalid quantity for {supply.name}.')
				return render(request, 'requisitions/request_form.html', context)
			if qty <= 0:
				messages.error(request, f'Quantity for {supply.name} must be greater than zero.')
				return render(request, 'requisitions/request_form.html', context)
			available_units = supply.boxes_count if supply.unit in ('pack', 'ream') else supply.quantity
			if qty > available_units:
				messages.error(request, f'Not enough stock for {supply.name}.')
				return render(request, 'requisitions/request_form.html', context)

			price_raw = request.POST.get(f'price_{supply.id}', '').strip()
			price_val = None
			if price_raw:
				try:
					price_val = Decimal(price_raw)
				except (InvalidOperation, ValueError):
					messages.error(request, f'Invalid price for {supply.name}.')
					return render(request, 'requisitions/request_form.html', context)
				if price_val < 0:
					messages.error(request, f'Price for {supply.name} must be non-negative.')
					return render(request, 'requisitions/request_form.html', context)

			item_date_needed_raw = request.POST.get(f'item_date_needed_{supply.id}', '').strip()
			item_date_needed = None
			if item_date_needed_raw:
				try:
					item_date_needed = date.fromisoformat(item_date_needed_raw)
				except ValueError:
					messages.error(request, f'Invalid item Date Needed for {supply.name}.')
					return render(request, 'requisitions/request_form.html', context)

			selections.append((supply, qty, price_val, item_date_needed))

		if not selections:
			messages.error(request, 'Please select at least one supply.')
			return render(request, 'requisitions/request_form.html', context)

		with transaction.atomic():
			supply_request = SupplyRequest.objects.create(
				user=request.user,
				requester_name=requester_name,
				organization_name=organization_name,
				date_needed=None,
				attention='',
				destination='',
				department=office_section,
				notes=notes,
			)
			items = [
				SupplyRequestItem(
					request=supply_request,
					supply=supply,
					quantity=qty,
					price_per_unit=price_val,
					item_date_needed=item_date_needed,
				)
				for supply, qty, price_val, item_date_needed in selections
			]
			SupplyRequestItem.objects.bulk_create(items)
		request.session.pop('selected_supplies', None)
		messages.success(request, 'Request submitted for approval.')
		return redirect('request_select_supplies')

	if not supplies:
		messages.info(request, 'Select supplies first.')
		return redirect('request_select_supplies')

	return render(request, 'requisitions/request_form.html', {
		'supplies': supplies,
		'query': query,
		'notes': '',
		'requester_name': request.user.get_full_name() or request.user.username,
		'organization_name': '',
		'office_section': '',
		'preselected': preselected,
	})


@login_required
def select_supplies(request):
	query = request.GET.get('q', '').strip()
	selected_category = request.GET.get('category', '').strip()
	supplies_qs = Supply.objects.all().order_by('name')
	if query:
		supplies_qs = supplies_qs.filter(
			Q(name__icontains=query)
			| Q(description__icontains=query)
			| Q(size_spec__icontains=query)
		)
	if selected_category:
		supplies_qs = supplies_qs.filter(category__iexact=selected_category)
	supplies = list(supplies_qs)

	# Group supplies by name so variants can be chosen via dropdown
	name_groups = {}
	for s in supplies:
		name_groups.setdefault(s.name, []).append(s)
	grouped_supplies = []
	for name in sorted(name_groups.keys()):
		variants = sorted(name_groups[name], key=lambda s: ((s.size_spec or '').lower(), s.id))
		grouped_supplies.append({'name': name, 'variants': variants})

	# Map for quick lookup by id during POST processing
	supply_map = {str(s.id): s for s in supplies}
	categories = [choice[0] for choice in Supply.CATEGORY_CHOICES]

	if request.method == 'POST':
		context = {
			'grouped_supplies': grouped_supplies,
			'query': query,
			'categories': categories,
			'selected_category': selected_category,
			'low_stock_threshold': LOW_STOCK_THRESHOLD,
		}
		selections = []
		for idx, group in enumerate(grouped_supplies):
			if not request.POST.get(f'select_{idx}'):
				continue
			selected_supply_id = request.POST.get(f'supply_choice_{idx}', '').strip()
			if not selected_supply_id:
				messages.error(request, f'Choose a size/spec for {group["name"]}.')
				return render(request, 'requisitions/select_supplies.html', context)
			supply = supply_map.get(selected_supply_id)
			if not supply:
				messages.error(request, f'Invalid selection for {group["name"]}.')
				return render(request, 'requisitions/select_supplies.html', context)
			qty_str = request.POST.get(f'quantity_{idx}', '').strip()
			if not qty_str:
				messages.error(request, f'Quantity required for {group["name"]}.')
				return render(request, 'requisitions/select_supplies.html', context)
			try:
				qty = int(qty_str)
			except ValueError:
				messages.error(request, f'Invalid quantity for {group["name"]}.')
				return render(request, 'requisitions/select_supplies.html', context)
			if qty <= 0:
				messages.error(request, f'Quantity for {group["name"]} must be greater than zero.')
				return render(request, 'requisitions/select_supplies.html', context)
			available = supply.boxes_count if supply.unit in ('pack', 'ream') else supply.quantity
			if qty > available:
				messages.error(request, f'Not enough stock for {supply.name} ({supply.size_spec or "Standard"}).')
				return render(request, 'requisitions/select_supplies.html', context)
			selections.append({'supply_id': supply.id, 'quantity': qty})

		if not selections:
			messages.error(request, 'Please select at least one supply (check the box, pick a size/spec, and enter quantity).')
			return render(request, 'requisitions/select_supplies.html', context)

		request.session['selected_supplies'] = selections
		messages.success(request, 'Items added. Continue to fill the request form.')
		return redirect('request_create')

	return render(request, 'requisitions/select_supplies.html', {
		'grouped_supplies': grouped_supplies,
		'query': query,
		'categories': categories,
		'selected_category': selected_category,
		'low_stock_threshold': LOW_STOCK_THRESHOLD,
	})


@login_required
def request_list(request):
	qs = SupplyRequest.objects.filter(is_archived=False).select_related('user', 'decided_by').prefetch_related('items__supply').order_by('-requested_at')
	if not request.user.is_staff:
		qs = qs.filter(user=request.user)
	pending = [r for r in qs if r.status == SupplyRequest.STATUS_PENDING]
	approved = [r for r in qs if r.status == SupplyRequest.STATUS_APPROVED]
	rejected = [r for r in qs if r.status == SupplyRequest.STATUS_REJECTED]
	return render(request, 'requisitions/request_list.html', {
		'all_requests': qs,
		'pending_requests': pending,
		'approved_requests': approved,
		'rejected_requests': rejected,
	})


@staff_required
def request_history(request):
	qs = (
		SupplyRequest.objects.select_related('user', 'decided_by')
		.prefetch_related('items__supply')
		.order_by('user__username', '-requested_at')
	)
	grouped = {}
	for req in qs:
		user = req.user
		uid = user.id
		if uid not in grouped:
			grouped[uid] = {
				'user': user,
				'display_name': user.get_full_name() or user.username,
				'requests': [],
				'counts': {'pending': 0, 'approved': 0, 'rejected': 0},
			}
		grouped[uid]['requests'].append(req)
		grouped[uid]['counts'][req.status] = grouped[uid]['counts'].get(req.status, 0) + 1
	user_groups = sorted(grouped.values(), key=lambda g: g['display_name'].lower())
	for group in user_groups:
		group['total_requests'] = len(group['requests'])
	return render(request, 'requisitions/request_history.html', {
		'user_groups': user_groups,
	})


@login_required
def request_history_user(request):
	qs = (
		SupplyRequest.objects.filter(user=request.user)
		.select_related('decided_by')
		.prefetch_related('items__supply')
		.order_by('-requested_at')
	)
	counts = {'pending': 0, 'approved': 0, 'rejected': 0}
	for r in qs:
		if r.status in counts:
			counts[r.status] += 1
	return render(request, 'requisitions/request_history_user.html', {
		'requests': qs,
		'counts': counts,
	})


@staff_required
def archive_request(request, pk):
	if request.method != 'POST':
		return redirect('request_list')
	supply_request = get_object_or_404(SupplyRequest, pk=pk)
	if supply_request.status == SupplyRequest.STATUS_PENDING:
		messages.error(request, 'Pending requests cannot be removed. Process them first.')
		return redirect('request_detail', pk=pk)
	if supply_request.is_archived:
		messages.info(request, 'Request already removed from the active list.')
		return redirect('request_list')
	supply_request.is_archived = True
	supply_request.save(update_fields=['is_archived'])
	messages.success(request, 'Request removed from active lists. It remains in history.')
	return redirect('request_list')


@staff_required
def request_detail(request, pk):
	supply_request = get_object_or_404(
		SupplyRequest.objects.select_related('user').prefetch_related('items__supply'), pk=pk
	)
	items = list(supply_request.items.select_related('supply'))
	shortages = []
	for item in items:
		supply = item.supply
		available = supply.boxes_count if supply.unit in ('pack', 'ream') else supply.quantity
		item.available_stock = available
		item.is_shortage = item.quantity > available
		if item.is_shortage:
			shortages.append({'name': supply.name, 'requested': item.quantity, 'available': available, 'unit': supply.unit})
	return render(request, 'requisitions/request_detail.html', {
		'req': supply_request,
		'items': items,
		'shortages': shortages,
	})


@login_required
def request_receipt(request, pk):
	req = get_object_or_404(
		SupplyRequest.objects.select_related('user', 'decided_by').prefetch_related('items__supply'), pk=pk
	)
	if (not request.user.is_staff) and req.user != request.user:
		messages.error(request, 'You do not have access to this receipt.')
		return redirect('request_list')
	if req.status != SupplyRequest.STATUS_APPROVED:
		messages.error(request, 'Receipt is available only after approval.')
		return redirect('request_list')
	items = list(req.items.select_related('supply'))
	return render(request, 'requisitions/request_receipt.html', {
		'req': req,
		'items': items,
		'generated_at': timezone.now(),
	})


@staff_required
def approve_request(request, pk):
	if request.method != 'POST':
		return redirect('request_list')
	supply_request = get_object_or_404(
		SupplyRequest.objects.select_related('user').prefetch_related('items__supply'), pk=pk
	)
	if supply_request.status != SupplyRequest.STATUS_PENDING:
		messages.info(request, 'Request already processed.')
		return redirect('request_list')

	with transaction.atomic():
		for item in supply_request.items.select_related('supply'):
			supply = item.supply
			available = supply.boxes_count if supply.unit in ('pack', 'ream') else supply.quantity
			if item.quantity > available:
				messages.error(request, f'Cannot approve: {supply.name} is low on stock (requested {item.quantity}, available {available}).')
				return redirect('request_list')

		for item in supply_request.items.select_related('supply'):
			supply = item.supply
			if supply.unit in ('pack', 'ream'):
				supply.boxes_count = max(0, supply.boxes_count - item.quantity)
				supply.quantity = supply.boxes_count
			else:
				supply.quantity = supply.quantity - item.quantity
			supply.save()

		supply_request.status = SupplyRequest.STATUS_APPROVED
		supply_request.decided_by = request.user
		supply_request.decision_at = timezone.now()
		supply_request.save()

	messages.success(request, 'Request approved and stock deducted.')
	return redirect('request_list')


@staff_required
def reject_request(request, pk):
	if request.method != 'POST':
		return redirect('request_list')
	supply_request = get_object_or_404(SupplyRequest, pk=pk)
	if supply_request.status != SupplyRequest.STATUS_PENDING:
		messages.info(request, 'Request already processed.')
		return redirect('request_list')

	supply_request.status = SupplyRequest.STATUS_REJECTED
	supply_request.decided_by = request.user
	supply_request.decision_at = timezone.now()
	supply_request.save()
	messages.success(request, 'Request rejected.')
	return redirect('request_list')

# Create your views here.
