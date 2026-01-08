from django import forms
from .models import DDSOperation, DDSArticle
from django import forms
from .models import CashTransfer # если вынес константу, иначе бери из CashMovement


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

# dds/forms.py
from decimal import Decimal
from django import forms
from django.utils import timezone

from .models import CashTransfer, CashRegister, CashMovement

def _balances_dict(register: CashRegister) -> dict:
    return {
        CashMovement.ACC_CASH: register.cash_balance or Decimal("0"),
        CashMovement.ACC_MKASSA: register.mkassa_balance or Decimal("0"),
        CashMovement.ACC_ZADATOK: register.zadatok_balance or Decimal("0"),
        CashMovement.ACC_OPTIMA: register.optima_balance or Decimal("0"),
    }

class CashTransferForm(forms.ModelForm):
    class Meta:
        model = CashTransfer
        fields = ["from_account", "to_account", "amount", "happened_at", "comment"]
        widgets = {
            "happened_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "comment": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, register: CashRegister | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._register = register

        # bootstrap
        self.fields["from_account"].widget.attrs["class"] = "form-select"
        self.fields["to_account"].widget.attrs["class"] = "form-select"
        self.fields["amount"].widget.attrs["class"] = "form-control"
        self.fields["happened_at"].widget.attrs["class"] = "form-control"
        self.fields["comment"].widget.attrs["class"] = "form-control"

        # choices с балансом
        labels = dict(CashMovement.ACCOUNT_CHOICES)
        bals = _balances_dict(register) if register else {}

        def fmt(acc: str) -> str:
            val = bals.get(acc, Decimal("0"))
            return f"{labels.get(acc, acc)} (баланс: {val:,.2f})"

        self.fields["from_account"].choices = [(acc, fmt(acc)) for acc, _ in CashMovement.ACCOUNT_CHOICES]
        self.fields["to_account"].choices = [(acc, fmt(acc)) for acc, _ in CashMovement.ACCOUNT_CHOICES]

    def clean(self):
        cleaned = super().clean()
        fa = cleaned.get("from_account")
        ta = cleaned.get("to_account")
        amount = cleaned.get("amount")

        if fa and ta and fa == ta:
            raise forms.ValidationError("Счёт списания и счёт зачисления должны отличаться.")

        if self._register and fa and amount:
            bals = _balances_dict(self._register)
            if bals.get(fa, Decimal("0")) < amount:
                raise forms.ValidationError(f"Недостаточно средств на счёте списания. Доступно: {bals.get(fa, Decimal('0')):,.2f}")

        # если не указали время — можно поставить сейчас
        if not cleaned.get("happened_at"):
            cleaned["happened_at"] = timezone.now()

        return cleaned
