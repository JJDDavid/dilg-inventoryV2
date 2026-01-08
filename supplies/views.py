from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth import update_session_auth_hash
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.auth import get_user_model

from requisitions.models import SupplyRequest, SupplyRequestItem

from .forms import IncomingSupplyForm, SupplyForm
from .models import IncomingSupply, Supply


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
def home(request):
	if request.user.is_staff:
		return redirect('dashboard')
	return redirect('request_create')


def signup_requestor(request):
	if request.user.is_authenticated:
		messages.info(request, 'You are already signed in.')
		return redirect('home')
	if request.method == 'POST':
		form = UserCreationForm(request.POST)
		if form.is_valid():
			user = form.save(commit=False)
			user.is_staff = False
			user.save()
			auth_login(request, user)
			messages.success(request, 'Account created. You can now request supplies.')
			return redirect('request_select_supplies')
	else:
		form = UserCreationForm()
	return render(request, 'registration/signup.html', {'form': form})


@login_required
def profile_settings(request):
	User = get_user_model()
	user = request.user

	class UsernameForm(forms.ModelForm):
		class Meta:
			model = User
			fields = ('username',)

	username_form = UsernameForm(request.POST or None, instance=user)
	password_form = PasswordChangeForm(user, request.POST or None, prefix='pwd') if request.method == 'POST' else PasswordChangeForm(user, prefix='pwd')

	if request.method == 'POST':
		action = request.POST.get('action') or 'both'
		username_valid = pwd_valid = False
		if action in ('username', 'both'):
			username_valid = username_form.is_valid()
			if username_valid:
				username_form.save()
				messages.success(request, 'Username updated.')
		if action in ('password', 'both'):
			pwd_valid = password_form.is_valid()
			if pwd_valid:
				password_form.save()
				update_session_auth_hash(request, user)
				messages.success(request, 'Password updated.')
		if username_valid or pwd_valid:
			return redirect('profile_settings')
		messages.error(request, 'Please correct the errors below.')

	context = {
		'username_form': username_form,
		'password_form': password_form,
	}
	return render(request, 'registration/profile_settings.html', context)


@staff_required
def dashboard(request):
	total_supplies = Supply.objects.count()
	total_quantity = Supply.objects.aggregate(total=Sum('quantity'))['total'] or 0
	low_stock = Supply.objects.filter(quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD).order_by('quantity', 'name')
	no_stock = Supply.objects.filter(quantity__lte=0).order_by('name')
	low_stock_count = low_stock.count()
	no_stock_count = no_stock.count()

	pending_requests_count = SupplyRequest.objects.filter(status=SupplyRequest.STATUS_PENDING, is_archived=False).count()

	top_requested = (
		SupplyRequestItem.objects.filter(request__status='approved')
		.values('supply__name')
		.annotate(total=Sum('quantity'))
		.order_by('-total')[:5]
	)

	monthly_outgoing = (
		SupplyRequestItem.objects.filter(request__status='approved')
		.annotate(month=TruncMonth('request__requested_at'))
		.values('month')
		.annotate(total=Sum('quantity'))
		.order_by('month')
	)

	chart_labels = [entry['month'].strftime('%b %Y') for entry in monthly_outgoing if entry['month']]
	chart_values = [entry['total'] for entry in monthly_outgoing]

	context = {
		'total_supplies': total_supplies,
		'total_quantity': total_quantity,
		'low_stock': low_stock,
		'no_stock': no_stock,
		'low_stock_count': low_stock_count,
		'no_stock_count': no_stock_count,
		'low_stock_threshold': LOW_STOCK_THRESHOLD,
		'top_requested': top_requested,
		'chart_labels': chart_labels,
		'chart_values': chart_values,
		'pending_requests_count': pending_requests_count,
	}
	return render(request, 'supplies/dashboard.html', context)


@staff_required
def supply_list(request):
	selected_category = request.GET.get('category', '').strip()
	query = request.GET.get('q', '').strip()
	supplies = Supply.objects.all()
	if selected_category:
		supplies = supplies.filter(category__iexact=selected_category)
	if query:
		supplies = supplies.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(size_spec__icontains=query))
	supplies = supplies.order_by('name')
	categories = [choice[0] for choice in Supply.CATEGORY_CHOICES]
	return render(request, 'supplies/supply_list.html', {
		'supplies': supplies,
		'categories': categories,
		'selected_category': selected_category,
		'query': query,
		'low_stock_threshold': LOW_STOCK_THRESHOLD,
	})


@staff_required
def supply_create(request):
	if request.method == 'POST':
		form = SupplyForm(request.POST)
		if form.is_valid():
			supply = form.save(commit=False)
			if supply.unit in ('pack', 'ream'):
				supply.quantity = supply.boxes_count or 0
			else:
				supply.quantity = (supply.boxes_count or 0) * (supply.items_per_box or 0)
			supply.save()
			messages.success(request, 'Supply added.')
			return redirect('supply_list')
	else:
		form = SupplyForm()
	return render(request, 'supplies/supply_form.html', {'form': form, 'title': 'Add Supply'})


@staff_required
def supply_update(request, pk):
	supply = get_object_or_404(Supply, pk=pk)
	if request.method == 'POST':
		form = SupplyForm(request.POST, instance=supply)
		if form.is_valid():
			updated = form.save(commit=False)
			if updated.unit in ('pack', 'ream'):
				updated.quantity = updated.boxes_count or 0
			else:
				updated.quantity = (updated.boxes_count or 0) * (updated.items_per_box or 0)
			updated.save()
			messages.success(request, 'Supply updated.')
			return redirect('supply_list')
	else:
		form = SupplyForm(instance=supply)
	return render(request, 'supplies/supply_form.html', {'form': form, 'title': 'Edit Supply'})


@staff_required
def supply_delete(request, pk):
	supply = get_object_or_404(Supply, pk=pk)
	if request.method == 'POST':
		supply.delete()
		messages.success(request, 'Supply deleted.')
		return redirect('supply_list')
	return render(request, 'supplies/supply_delete.html', {'supply': supply})


@staff_required
def record_incoming(request):
	incoming_list = IncomingSupply.objects.select_related('supply').order_by('-date_added')
	if request.method == 'POST':
		form = IncomingSupplyForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'Incoming supply recorded. Mark as received when it arrives to add to inventory.')
			return redirect('record_incoming')
	else:
		form = IncomingSupplyForm()

	return render(request, 'supplies/incoming_form.html', {
		'form': form,
		'incoming_list': incoming_list,
	})


@staff_required
def receive_incoming(request, pk):
	incoming = get_object_or_404(IncomingSupply.objects.select_related('supply'), pk=pk)
	if incoming.status == IncomingSupply.STATUS_RECEIVED:
		messages.info(request, 'This incoming supply is already received.')
		return redirect('record_incoming')

	supply = incoming.supply
	# Update boxes_count and quantity based on supply unit
	if supply.unit in ('pack', 'ream'):
		supply.boxes_count = supply.boxes_count + incoming.quantity
		supply.quantity = supply.boxes_count
	else:
		delta_boxes = 0
		if supply.items_per_box:
			delta_boxes = incoming.quantity // supply.items_per_box
		supply.boxes_count = supply.boxes_count + delta_boxes
		supply.quantity = supply.quantity + incoming.quantity
	supply.save()

	incoming.status = IncomingSupply.STATUS_RECEIVED
	incoming.received_at = timezone.now()
	incoming.save(update_fields=['status', 'received_at'])

	messages.success(request, 'Items added to inventory.')
	return redirect('record_incoming')

# Create your views here.
