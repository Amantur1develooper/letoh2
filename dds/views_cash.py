# dds/views_cash.py (или pms/views.py)

from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from dds.models import Hotel, CashMovement
from dds.cash_services import transfer_between_accounts, CashTransferError

try:
    from dds.utils import _user_hotels_qs
except Exception:
    def _user_hotels_qs(user):
        return Hotel.objects.filter(is_active=True)

class TransferForm(forms.Form):
    from_account = forms.ChoiceField(choices=CashMovement.ACCOUNT_CHOICES, label="Со счета")
    to_account = forms.ChoiceField(choices=CashMovement.ACCOUNT_CHOICES, label="На счет")
    amount = forms.DecimalField(min_value=Decimal("0.01"), decimal_places=2, max_digits=12, label="Сумма")
    happened_at = forms.DateTimeField(required=False, label="Дата/время")
    comment = forms.CharField(required=False, label="Комментарий")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("from_account") == cleaned.get("to_account"):
            raise forms.ValidationError("Счета должны отличаться.")
        return cleaned


@login_required
def transfer_create(request):
    hotels = _user_hotels_qs(request.user)
    hotel_id = request.GET.get("hotel") or ""
    if hotel_id:
        hotel = get_object_or_404(hotels, id=hotel_id)
    else:
        hotel = hotels.first()

    if not hotel:
        messages.error(request, "Нет доступных отелей.")
        return redirect("pms:board")

    if request.method == "POST":
        form = TransferForm(request.POST)
        if form.is_valid():
            try:
                transfer_between_accounts(
                    hotel=hotel,
                    from_account=form.cleaned_data["from_account"],
                    to_account=form.cleaned_data["to_account"],
                    amount=form.cleaned_data["amount"],
                    happened_at=form.cleaned_data["happened_at"] or timezone.now(),
                    comment=form.cleaned_data["comment"] or "",
                    user=request.user,
                )
                messages.success(request, "Перевод выполнен.")
                return redirect(f"{request.path}?hotel={hotel.id}")
            except CashTransferError as e:
                messages.error(request, str(e))
    else:
        form = TransferForm(initial={"happened_at": timezone.now()})

    return render(request, "dds/transfer_form.html", {"form": form, "hotel": hotel, "hotels": hotels})


# dds/views.py
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CashTransferForm
from .services import create_cash_transfer
from .models import Hotel

try:
    from dds.utils import _user_hotels_qs
except Exception:
    def _user_hotels_qs(user):
        return Hotel.objects.filter(is_active=True)
# dds/views.py
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

from .models import Hotel, CashRegister, CashMovement, CashTransfer
from .forms import CashTransferForm, _balances_dict

@login_required
def cash_transfer_create(request, hotel_id: int):
    hotel = get_object_or_404(Hotel, id=hotel_id)

    register, _ = CashRegister.objects.get_or_create(hotel=hotel)

    if request.method == "POST":
        form = CashTransferForm(request.POST, register=register)
        if form.is_valid():
            with transaction.atomic():
                transfer: CashTransfer = form.save(commit=False)
                transfer.hotel = hotel
                transfer.register = register
                transfer.created_by = request.user
                transfer.save()

                fa = form.cleaned_data["from_account"]
                ta = form.cleaned_data["to_account"]
                amount = form.cleaned_data["amount"]
                happened_at = form.cleaned_data["happened_at"]
                comment = form.cleaned_data.get("comment") or ""

                # движения денег
                CashMovement.objects.create(
                    register=register, hotel=hotel,
                    direction=CashMovement.OUT, account=fa,
                    amount=amount, happened_at=happened_at,
                    comment=f"Перевод: {fa} -> {ta}. {comment}".strip(),
                    created_by=request.user,
                    transfer=transfer,
                )
                CashMovement.objects.create(
                    register=register, hotel=hotel,
                    direction=CashMovement.IN, account=ta,
                    amount=amount, happened_at=happened_at,
                    comment=f"Перевод: {fa} -> {ta}. {comment}".strip(),
                    created_by=request.user,
                    transfer=transfer,
                )

                # обновляем балансы кассы
                if fa == CashMovement.ACC_CASH:
                    register.cash_balance -= amount
                elif fa == CashMovement.ACC_MKASSA:
                    register.mkassa_balance -= amount
                elif fa == CashMovement.ACC_ZADATOK:
                    register.zadatok_balance -= amount
                elif fa == CashMovement.ACC_OPTIMA:
                    register.optima_balance -= amount

                if ta == CashMovement.ACC_CASH:
                    register.cash_balance += amount
                elif ta == CashMovement.ACC_MKASSA:
                    register.mkassa_balance += amount
                elif ta == CashMovement.ACC_ZADATOK:
                    register.zadatok_balance += amount
                elif ta == CashMovement.ACC_OPTIMA:
                    register.optima_balance += amount

                register.save(update_fields=["cash_balance", "mkassa_balance", "zadatok_balance", "optima_balance", "updated_at"])

            messages.success(request, "Перевод выполнен.")
            # ✅ редирект в детали отеля (поставь свой urlname)
            try:
                return redirect(reverse("dds:hotel_detail", args=[hotel.id]))
            except Exception:
                url = reverse("dds:dds_dashboard")
                return redirect(f"{url}?hotel={hotel.id}")
    else:
        form = CashTransferForm(register=register)

    balances = _balances_dict(register)

    return render(request, "dds/cash_transfer_form.html", {
        "hotel": hotel,
        "form": form,
        "register": register,
        "balances": balances,
    })
