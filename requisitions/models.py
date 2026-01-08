from django.conf import settings
from django.db import models
from django.utils import timezone

from supplies.models import Supply


class SupplyRequest(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_APPROVED = 'approved'
	STATUS_REJECTED = 'rejected'

	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_APPROVED, 'Approved'),
		(STATUS_REJECTED, 'Rejected'),
	]

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	requested_at = models.DateTimeField(auto_now_add=True)
	requester_name = models.CharField(max_length=255, blank=True)
	organization_name = models.CharField(max_length=255, blank=True)
	date_needed = models.DateField(null=True, blank=True)
	attention = models.CharField(max_length=255, blank=True)
	destination = models.CharField(max_length=255, blank=True)
	department = models.CharField(max_length=255, blank=True)
	notes = models.TextField(blank=True)
	decision_at = models.DateTimeField(null=True, blank=True)
	decided_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='decided_requests',
	)
	is_archived = models.BooleanField(default=False)

	def __str__(self):
		return f"Request #{self.id} by {self.user} ({self.status})"


class SupplyRequestItem(models.Model):
	request = models.ForeignKey(SupplyRequest, on_delete=models.CASCADE, related_name='items')
	supply = models.ForeignKey(Supply, on_delete=models.CASCADE, related_name='request_items')
	quantity = models.PositiveIntegerField()
	price_per_unit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
	item_date_needed = models.DateField(null=True, blank=True)

	def __str__(self):
		return f"{self.quantity} x {self.supply.name}"

	@property
	def total_cost(self):
		if self.price_per_unit is None:
			return None
		return self.price_per_unit * self.quantity
