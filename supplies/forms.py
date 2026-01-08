from django import forms

from .models import IncomingSupply, Supply


class SupplyForm(forms.ModelForm):
    class Meta:
        model = Supply
        fields = ['name', 'size_spec', 'description', 'category', 'boxes_count', 'items_per_box', 'quantity', 'unit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Bond paper A4'}),
            'size_spec': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Size / Specification'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Short description or notes'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'boxes_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'No. of boxes'}),
            'items_per_box': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Items per box'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': '0'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
        }


class IncomingSupplyForm(forms.ModelForm):
    boxes_count = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'No. of boxes'}),
        label='No. of Boxes'
    )

    class Meta:
        model = IncomingSupply
        fields = ['supply', 'boxes_count', 'expected_date', 'notes']
        widgets = {
            'supply': forms.Select(attrs={'class': 'form-select'}),
            'expected_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Supplier, PO, tracking, or remarks'}),
        }

    def clean(self):
        data = super().clean()
        supply = data.get('supply')
        boxes = data.get('boxes_count')

        if boxes is None:
            self.add_error('boxes_count', 'Please enter the number of boxes.')
            return data

        if supply is None:
            return data

        if supply.unit in ('pack', 'ream'):
            quantity = boxes
        else:
            per_box = supply.items_per_box or 0
            if per_box <= 0:
                self.add_error('boxes_count', 'Items per box not set for this supply. Update the supply first.')
                return data
            quantity = boxes * per_box

        if quantity <= 0:
            self.add_error('boxes_count', 'Quantity must be greater than zero.')
        else:
            data['quantity'] = quantity

        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.quantity = self.cleaned_data.get('quantity') or obj.quantity
        if commit:
            obj.save()
        return obj
