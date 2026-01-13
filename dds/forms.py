from django import forms
from .models import DDSOperation, DDSArticle
from django import forms
from .models import CashTransfer # если вынес константу, иначе бери из CashMovement

from django import forms
from django.db.models import Q
from django.core.exceptions import ValidationError

from .models import DDSOperation, DDSArticle
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import DDSOperation, DDSArticle
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import DDSOperation, DDSArticle, Hotel

from django import forms
from django.core.exceptions import ValidationError

from .models import DDSOperation, DDSArticle, Hotel

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import DDSOperation, DDSArticle, Hotel


class DDSOperationForm(forms.ModelForm):
    class Meta:
        model = DDSOperation
        fields = ["hotel", "article", "amount", "happened_at", "method", "counterparty", "source", "comment"]

    def __init__(self, *args, hotel=None, kind=None, **kwargs):
        super().__init__(*args, **kwargs)

        # 1) Определяем выбранный отель (важно!)
        selected_hotel = hotel

        if selected_hotel is None:
            hotel_id = None
            if self.is_bound:
                hotel_id = self.data.get("hotel")
            else:
                hotel_id = self.initial.get("hotel")

            if hotel_id:
                try:
                    selected_hotel = Hotel.objects.get(pk=hotel_id)
                except Hotel.DoesNotExist:
                    selected_hotel = None

        # 2) Базовый queryset статей
        qs = DDSArticle.objects.filter(is_active=True)

        if kind in (DDSArticle.INCOME, DDSArticle.EXPENSE):
            qs = qs.filter(kind=kind)

        # 3) ✅ ГЛАВНОЕ: фильтр по отелю
        # показываем:
        # - статьи привязанные к выбранному отелю
        # - ИЛИ “общие” статьи (у которых hotels пустой)
        if selected_hotel:
            qs = qs.filter(Q(hotels=selected_hotel) | Q(hotels__isnull=True)).distinct()
        else:
            # если отель не выбран — можно показывать только общие
            # (чтобы не было “всё подряд”)
            qs = qs.filter(hotels__isnull=True).distinct()

        self.fields["article"].queryset = qs
        self._filter_hotel = selected_hotel

    def clean_article(self):
        article = self.cleaned_data.get("article")
        hotel = self.cleaned_data.get("hotel") or getattr(self, "_filter_hotel", None)

        if not article:
            return article
        if not hotel:
            raise ValidationError("Сначала выберите отель.")

        # ✅ если у статьи есть ограничения по отелям — проверяем
        if article.hotels.exists() and not article.hotels.filter(pk=hotel.pk).exists():
            raise ValidationError("Эта статья не доступна для выбранного отеля.")

        return article

# class DDSOperationForm(forms.ModelForm):
#     class Meta:
#         model = DDSOperation
#         fields = ["hotel", "article", "amount", "happened_at", "method", "counterparty", "source", "comment"]

#     def __init__(self, *args, hotel=None, kind=None, **kwargs):
#         super().__init__(*args, **kwargs)

#         # по умолчанию — ничего не показываем
#         self.fields["article"].queryset = DDSArticle.objects.none()
#         self.fields["article"].disabled = True
#         self.fields["article"].help_text = "Сначала выберите отель"

#         selected_hotel = hotel

#         # если hotel не передали — пробуем взять из формы
#         if selected_hotel is None:
#             hotel_id = None

#             if self.is_bound:
#                 hotel_id = self.data.get("hotel")
#             else:
#                 hotel_id = self.initial.get("hotel")

#             if hotel_id:
#                 try:
#                     selected_hotel = Hotel.objects.get(pk=hotel_id)
#                 except Hotel.DoesNotExist:
#                     selected_hotel = None

#         qs = DDSArticle.objects.filter(is_active=True)

#         # фильтр доход/расход
#         if kind in (DDSArticle.INCOME, DDSArticle.EXPENSE):
#             qs = qs.filter(kind=kind)

#         # ✅ СТРОГО: показываем только те, где выбранный отель есть в M2M
#         if selected_hotel:
#             qs = qs.filter(hotels=selected_hotel).distinct()
#             self.fields["article"].queryset = qs
#             self.fields["article"].disabled = False
#             self.fields["article"].help_text = ""

#         self._filter_hotel = selected_hotel

#     def clean_article(self):
#         article = self.cleaned_data.get("article")
#         hotel = self.cleaned_data.get("hotel") or getattr(self, "_filter_hotel", None)

#         if not hotel:
#             raise ValidationError("Сначала выберите отель.")

#         if not article:
#             return article

#         # ✅ Жёсткая проверка на сервере
#         if not article.hotels.filter(pk=hotel.pk).exists():
#             raise ValidationError("Эта статья не доступна для выбранного отеля.")

#         return article

# class DDSOperationForm(forms.ModelForm):
#     class Meta:
#         model = DDSOperation
#         fields = ["hotel", "article", "amount", "happened_at", "method", "counterparty", "source", "comment"]

#     def __init__(self, *args, hotel=None, kind=None, **kwargs):
#         super().__init__(*args, **kwargs)

#         # 1) пробуем взять отель из kwargs (из view)
#         selected_hotel = hotel

#         # 2) если не передали — пробуем взять из формы (POST/GET)
#         if selected_hotel is None:
#             hotel_id = None
#             if self.is_bound:
#                 hotel_id = self.data.get("hotel")
#             else:
#                 hotel_id = self.initial.get("hotel")

#             if hotel_id:
#                 try:
#                     selected_hotel = Hotel.objects.get(pk=hotel_id)
#                 except Hotel.DoesNotExist:
#                     selected_hotel = None

#         qs = DDSArticle.objects.filter(is_active=True)

#         # фильтр по виду доход/расход
#         if kind in (DDSArticle.INCOME, DDSArticle.EXPENSE):
#             qs = qs.filter(kind=kind)

#         # ✅ СТРОГО: если отель не определён — не показываем ничего
#         if selected_hotel:
#             qs = qs.filter(hotels=selected_hotel).distinct()
#         else:
#             qs = qs.none()

#         self.fields["article"].queryset = qs
#         self._filter_hotel = selected_hotel  # для clean_article

#     def clean_article(self):
#         article = self.cleaned_data.get("article")
#         hotel = self.cleaned_data.get("hotel") or getattr(self, "_filter_hotel", None)

#         if not article:
#             return article

#         # если отель не выбран — запрещаем
#         if not hotel:
#             raise ValidationError("Сначала выберите отель.")

#         # ✅ строго: статья должна быть привязана к отелю
#         if not article.hotels.filter(pk=hotel.pk).exists():
#             raise ValidationError("Эта статья не доступна для выбранного отеля.")

#         return article

# class DDSOperationForm(forms.ModelForm):
#     class Meta:
#         model = DDSOperation
#         fields = ["hotel", "article", "amount", "happened_at", "method", "counterparty", "source", "comment"]

#     def __init__(self, *args, hotel=None, kind=None, **kwargs):
#         super().__init__(*args, **kwargs)

#         qs = DDSArticle.objects.filter(is_active=True)

#         if kind in (DDSArticle.INCOME, DDSArticle.EXPENSE):
#             qs = qs.filter(kind=kind)

#         if hotel:
#             # ✅ строгий режим (только статьи выбранного отеля)
#             qs = qs.filter(hotels=hotel).distinct()

#             # ✅ если нужны ещё “общие статьи”, включи вместо строки выше:
#             # qs = qs.filter(Q(hotels=hotel) | Q(hotels__isnull=True)).distinct()

#         self.fields["article"].queryset = qs
#         self._filter_hotel = hotel

#     def clean_article(self):
#         article = self.cleaned_data.get("article")
#         hotel = self.cleaned_data.get("hotel") or getattr(self, "_filter_hotel", None)

#         if not article or not hotel:
#             return article

#         # если у статьи указаны отели — проверяем доступ
#         if article.hotels.exists() and not article.hotels.filter(pk=hotel.pk).exists():
#             raise ValidationError("Эта статья не доступна для выбранного отеля.")

#         return article

# class DDSOperationForm(forms.ModelForm):
#     class Meta:
#         model = DDSOperation
#         fields = ["hotel", "article", "amount", "happened_at", "method", "counterparty", "source", "comment"]

#     def __init__(self, *args, hotel=None, kind=None, **kwargs):
#         super().__init__(*args, **kwargs)

#         qs = DDSArticle.objects.filter(is_active=True)

#         # ✅ если хотим разделить доход/расход кнопками
#         if kind in (DDSArticle.INCOME, DDSArticle.EXPENSE):
#             qs = qs.filter(kind=kind)

#         # ✅ фильтр по отелю:
#         # показываем (1) статьи, привязанные к отелю
#         # и (2) "общие" статьи (где hotels пустой)
#         if hotel:
#             qs = qs.filter(hotels=hotel).distinct()

#             # qs = qs.filter(Q(hotels=hotel) | Q(hotels__isnull=True)).distinct()

#         self.fields["article"].queryset = qs

#         # чтобы в clean_article знать выбранный отель
#         self._filter_hotel = hotel

#     def clean_article(self):
#         article = self.cleaned_data.get("article")
#         hotel = self.cleaned_data.get("hotel") or getattr(self, "_filter_hotel", None)

#         if not article or not hotel:
#             return article

#         # ✅ если у статьи указаны отели — проверяем доступ
#         if article.hotels.exists() and not article.hotels.filter(pk=hotel.pk).exists():
#             raise ValidationError("Эта статья не доступна для выбранного отеля.")
#         return article

# class DDSOperationForm(forms.ModelForm):
#     class Meta:
#         model = DDSOperation
#         fields = ["hotel", "article", "amount", "happened_at", "method", "counterparty", "comment", "source"]
#         widgets = {
#             "happened_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
#             "comment": forms.Textarea(attrs={"rows": 2}),
#         }

#     def clean_amount(self):
#         amount = self.cleaned_data["amount"]
#         if amount <= 0:
#             raise forms.ValidationError("Сумма должна быть больше 0.")
#         return amount


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

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import DDSOperation, DDSArticle, DDSCategory


class DDSOpCreateForm(forms.ModelForm):
    # поле категории нужно только для queryset в шаблоне (ты его так используешь)
    category = forms.ModelChoiceField(
        queryset=DDSCategory.objects.none(),
        required=False,
        label="Категория",
    )

    class Meta:
        model = DDSOperation
        fields = ["article", "amount", "happened_at", "method", "counterparty", "comment"]
        # source у тебя в модели есть, но в этой “быстрой форме” ты его не показываешь

    def __init__(self, *args, kind=None, category_id=None, hotel=None, **kwargs):
        super().__init__(*args, **kwargs)

        # --- Категории для выпадающего списка (в GET форме) ---
        cats = DDSCategory.objects.filter(is_active=True)

        if kind in (DDSArticle.INCOME, DDSArticle.EXPENSE):
            cats = cats.filter(kind=kind)

        self.fields["category"].queryset = cats.select_related("parent").order_by("parent_id", "name")

        # чтобы выбранная категория подсвечивалась
        if category_id:
            try:
                self.fields["category"].initial = int(category_id)
            except Exception:
                pass

        # --- Статьи (главная часть) ---
        qs = DDSArticle.objects.filter(is_active=True)

        # 1) по виду (доход/расход)
        if kind in (DDSArticle.INCOME, DDSArticle.EXPENSE):
            qs = qs.filter(kind=kind)

        # 2) если категория не выбрана — НЕ показываем ничего
        if category_id:
            qs = qs.filter(category_id=category_id)
        else:
            qs = qs.none()

        # 3) ✅ фильтр по отелю:
        # (hotels пустой) ИЛИ (hotels содержит этот отель)
        if hotel:
            qs = qs.filter(Q(hotels=hotel) | Q(hotels__isnull=True)).distinct()
        else:
            # если отель не передали — показываем только “общие”
            qs = qs.filter(hotels__isnull=True).distinct()

        self.fields["article"].queryset = qs.select_related("category", "category__parent").order_by("name")
        self._hotel = hotel

    def clean_article(self):
        article = self.cleaned_data.get("article")
        if not article:
            return article

        # ✅ защита: если статья ограничена отелями — проверяем доступ
        if self._hotel and article.hotels.exists() and not article.hotels.filter(pk=self._hotel.pk).exists():
            raise ValidationError("Эта статья не доступна для выбранного отеля.")

        return article

# class DDSOpCreateForm(forms.ModelForm):
#     # поле "категория" не в модели DDSOperation, но нужно для удобства
#     category = forms.ModelChoiceField(
#         queryset=DDSCategory.objects.none(),
#         required=True,
#         label="Категория",
#         empty_label="— выберите категорию —",
#     )

#     happened_at = forms.DateTimeField(
#         required=True,
#         label="Дата/время",
#         widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
#         input_formats=["%Y-%m-%dT%H:%M"],  # важно для datetime-local
#     )

#     class Meta:
#         model = DDSOperation
#         fields = [
#             "category",
#             "article",
#             "amount",
#             "happened_at",
#             "method",
#             "counterparty",
#             "comment",
#         ]
#         widgets = {
#             "comment": forms.Textarea(attrs={"rows": 2}),
#         }

#     def __init__(self, *args, kind: str, category_id=None, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.kind = kind

#         # категории только нужного вида
#         self.fields["category"].queryset = (
#             DDSCategory.objects.filter(is_active=True, kind=kind)
#             .order_by("parent_id", "name")
#         )

#         # статьи только нужного вида, и строго по категории
#         articles_qs = DDSArticle.objects.filter(is_active=True, kind=kind)

#         if category_id:
#             try:
#                 cid = int(category_id)
#                 articles_qs = articles_qs.filter(category_id=cid)
#                 self.fields["category"].initial = cid
#             except Exception:
#                 articles_qs = DDSArticle.objects.none()
#         else:
#             # пока не выбрали категорию — статей не показываем
#             articles_qs = DDSArticle.objects.none()

#         self.fields["article"].queryset = articles_qs.order_by("name")

#         # дата по умолчанию "сейчас"
#         if not self.initial.get("happened_at"):
#             now = timezone.localtime(timezone.now())
#             self.initial["happened_at"] = now.strftime("%Y-%m-%dT%H:%M")

#     def clean(self):
#         cleaned = super().clean()
#         cat = cleaned.get("category")
#         art = cleaned.get("article")

#         if cat and art and art.category_id != cat.id:
#             self.add_error("article", "Выбранная статья не относится к этой категории.")
#         return cleaned
