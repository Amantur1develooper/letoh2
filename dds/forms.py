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


# dds/forms.py
from django import forms
from .models import DDSOperation, DDSCategory, DDSArticle

class DDSQuickOpForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=DDSCategory.objects.none(),
        required=False,
        label="Категория",
    )

    class Meta:
        model = DDSOperation
        fields = ["article", "amount", "happened_at", "method", "counterparty", "comment"]
        widgets = {
            "happened_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "comment": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, kind: str, hotel=None, category_id=None, **kwargs):
        super().__init__(*args, **kwargs)

        # категории только нужного вида (доход/расход)
        self.fields["category"].queryset = DDSCategory.objects.filter(is_active=True, kind=kind).order_by("parent_id", "name")

        # статьи только нужного вида и (по умолчанию) активные
        qs = DDSArticle.objects.filter(is_active=True, kind=kind)

        # если выбрали категорию — сужаем статьи
        if category_id:
            try:
                cat_id = int(category_id)
                # категория + её дети (2 уровня достаточно для MVP)
                qs = qs.filter(category_id=cat_id) | qs.filter(category__parent_id=cat_id)
            except Exception:
                pass

        self.fields["article"].queryset = qs.select_related("category").order_by("category_id", "name")
        self.fields["article"].label = "Статья"

        # чуть удобнее отображение
        self.fields["amount"].widget.attrs.update({"placeholder": "0.00"})


# dds/forms.py
from django import forms
from django.db.models import Q
from .models import DDSOperation, DDSCategory, DDSArticle

class DDSOpForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=DDSCategory.objects.none(),
        required=False,
        label="Категория",
        empty_label="— выбери категорию —",
    )

    class Meta:
        model = DDSOperation
        fields = ["category", "article", "amount", "happened_at", "method", "counterparty", "comment"]
        widgets = {
            "happened_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "comment": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, kind: str, category_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind

        # Категории только нужного вида (доход/расход)
        self.fields["category"].queryset = (
            DDSCategory.objects.filter(is_active=True, kind=kind)
            .order_by("parent_id", "name")
        )

        # Статьи только нужного вида
        articles = DDSArticle.objects.filter(is_active=True, kind=kind)

        # ✅ Строго: только статьи выбранной категории
        if category_id:
            try:
                cid = int(category_id)
                articles = articles.filter(category_id=cid)
            except Exception:
                pass

        self.fields["article"].queryset = articles.select_related("category").order_by("name")
        self.fields["article"].label = "Статья"

    def clean(self):
        cleaned = super().clean()
        cat = cleaned.get("category")
        art = cleaned.get("article")

        # ✅ защита: статья обязана принадлежать выбранной категории
        if cat and art and art.category_id != cat.id:
            self.add_error("article", "Эта статья не относится к выбранной категории.")
        return cleaned


# dds/forms.py
from django import forms
from django.utils import timezone

from .models import DDSOperation, DDSCategory, DDSArticle


class DDSOpCreateForm(forms.ModelForm):
    # поле "категория" не в модели DDSOperation, но нужно для удобства
    category = forms.ModelChoiceField(
        queryset=DDSCategory.objects.none(),
        required=True,
        label="Категория",
        empty_label="— выберите категорию —",
    )

    happened_at = forms.DateTimeField(
        required=True,
        label="Дата/время",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],  # важно для datetime-local
    )

    class Meta:
        model = DDSOperation
        fields = [
            "category",
            "article",
            "amount",
            "happened_at",
            "method",
            "counterparty",
            "comment",
        ]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, kind: str, category_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind

        # категории только нужного вида
        self.fields["category"].queryset = (
            DDSCategory.objects.filter(is_active=True, kind=kind)
            .order_by("parent_id", "name")
        )

        # статьи только нужного вида, и строго по категории
        articles_qs = DDSArticle.objects.filter(is_active=True, kind=kind)

        if category_id:
            try:
                cid = int(category_id)
                articles_qs = articles_qs.filter(category_id=cid)
                self.fields["category"].initial = cid
            except Exception:
                articles_qs = DDSArticle.objects.none()
        else:
            # пока не выбрали категорию — статей не показываем
            articles_qs = DDSArticle.objects.none()

        self.fields["article"].queryset = articles_qs.order_by("name")

        # дата по умолчанию "сейчас"
        if not self.initial.get("happened_at"):
            now = timezone.localtime(timezone.now())
            self.initial["happened_at"] = now.strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        cat = cleaned.get("category")
        art = cleaned.get("article")

        if cat and art and art.category_id != cat.id:
            self.add_error("article", "Выбранная статья не относится к этой категории.")
        return cleaned
