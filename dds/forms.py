from django import forms
from .models import DDSOperation, DDSArticle


class DDSOperationForm(forms.ModelForm):
    class Meta:
        model = DDSOperation
        fields = ["hotel", "article", "amount", "happened_at", "method", "counterparty", "comment", "source"]
        widgets = {
            "happened_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "comment": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Сумма должна быть больше 0.")
        return amount


class DDSArticleForm(forms.ModelForm):
    class Meta:
        model = DDSArticle
        fields = ["kind", "name", "is_active"]


from django import forms
from .models import Hotel

class HotelForm(forms.ModelForm):
    class Meta:
        model = Hotel
        fields = ["name", "is_active"]

from .models import CashIncasso

class CashIncassoForm(forms.ModelForm):
    class Meta:
        model = CashIncasso
        fields = ["amount", "happened_at", "method", "comment"]
        widgets = {
            "happened_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "comment": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_amount(self):
        a = self.cleaned_data["amount"]
        if a <= 0:
            raise forms.ValidationError("Сумма должна быть больше 0.")
        return a
