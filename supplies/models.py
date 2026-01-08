from django.db import models
from django.utils import timezone


class Supply(models.Model):
	CATEGORY_CHOICES = (
		('Writing Supplies', 'Writing Supplies'),
		('Paper Supplies', 'Paper Supplies'),
		('Filing Supplies', 'Filing Supplies'),
		('Printing Supplies', 'Printing Supplies'),
		('Desk Accessories', 'Desk Accessories'),
		('IT Office Accessories', 'IT Office Accessories'),
		('Official Forms & Stationery', 'Official Forms & Stationery'),
		('Office Maintenance Supplies', 'Office Maintenance Supplies'),
	)

	UNIT_CHOICES = (
		('pc', 'pc'),
		('pack', 'pack'),
		('box', 'box'),
		('ream', 'ream'),
		('sheet', 'sheet'),
		('set', 'set'),
		('bottle', 'bottle'),
		('roll', 'roll'),
		('can', 'can'),
	)

	name = models.CharField(max_length=255)
	description = models.TextField(blank=True)
	category = models.CharField(max_length=100, blank=True, choices=CATEGORY_CHOICES)
	size_spec = models.CharField(max_length=255, blank=True)
	boxes_count = models.PositiveIntegerField(default=0)
	items_per_box = models.PositiveIntegerField(default=0)
	quantity = models.PositiveIntegerField(default=0)
	unit = models.CharField(max_length=50, choices=UNIT_CHOICES)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ('name', 'size_spec')

	def __str__(self):
		return f"{self.name} ({self.quantity} {self.unit})"


class IncomingSupply(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_RECEIVED = 'received'
	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_RECEIVED, 'Received'),
	]

	supply = models.ForeignKey(Supply, on_delete=models.CASCADE, related_name='incoming')
	quantity = models.PositiveIntegerField()
	expected_date = models.DateField(null=True, blank=True)
	notes = models.TextField(blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	date_added = models.DateTimeField(default=timezone.now)
	received_at = models.DateTimeField(null=True, blank=True)

	def __str__(self):
		return f"Incoming {self.quantity} {self.supply.unit} {self.supply.name}"
