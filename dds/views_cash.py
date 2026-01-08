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

# dds/views.py
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import DDSQuickOpForm
from .models import Hotel, CashRegister, CashMovement, DDSOperation, DDSArticle

# если у тебя есть ограничение отелей по пользователю — используй своё
from .utils import user_hotels_qs


def _account_field_from_method(method: str) -> str:
    # method в DDSOperation = cash/mkassa/zadatok/optima
    return {
        DDSOperation.CASH: "cash_balance",
        DDSOperation.MKASSA: "mkassa_balance",
        DDSOperation.ZADATOK: "zadatok_balance",
        DDSOperation.OPTIMA: "optima_balance",
    }[method]


def _cashmovement_account_from_method(method: str) -> str:
    return {
        DDSOperation.CASH: CashMovement.ACC_CASH,
        DDSOperation.MKASSA: CashMovement.ACC_MKASSA,
        DDSOperation.ZADATOK: CashMovement.ACC_ZADATOK,
        DDSOperation.OPTIMA: CashMovement.ACC_OPTIMA,
    }[method]


# @login_required
# def dds_op_add(request, hotel_id: int, kind: str):
#     hotels = user_hotels_qs(request.user)
#     hotel = get_object_or_404(hotels, id=hotel_id)

#     register, _ = CashRegister.objects.get_or_create(hotel=hotel)

#     # чтобы category “держалась” без перезагрузки формы
#     category_id = request.GET.get("category") or (request.POST.get("category") if request.method == "POST" else "")

#     if request.method == "POST":
#         form = DDSQuickOpForm(request.POST, kind=kind, hotel=hotel, category_id=category_id)
#         if form.is_valid():
#             op: DDSOperation = form.save(commit=False)
#             op.hotel = hotel
#             op.created_by = request.user
#             if not op.happened_at:
#                 op.happened_at = timezone.now()

#             direction = CashMovement.IN if kind == DDSArticle.INCOME else CashMovement.OUT
#             account = _cashmovement_account_from_method(op.method)

#             with transaction.atomic():
#                 op.save()

#                 CashMovement.objects.create(
#                     register=register,
#                     hotel=hotel,
#                     direction=direction,
#                     account=account,
#                     amount=op.amount,
#                     happened_at=op.happened_at,
#                     comment=f"DDS #{op.id}: {op.article.name}",
#                     dds_operation=op,
#                     created_by=request.user,
#                 )

#                 field = _account_field_from_method(op.method)
#                 sign = 1 if direction == CashMovement.IN else -1
#                 CashRegister.objects.filter(pk=register.pk).update(**{field: F(field) + sign * op.amount})

#             # ✅ после сохранения — в детали отеля
#             return redirect("dds:hotel_detail", hotel.id)
#     else:
#         form = DDSQuickOpForm(kind=kind, hotel=hotel, category_id=category_id)
#         # проставим category если пришла
#         if category_id:
#             try:
#                 form.fields["category"].initial = int(category_id)
#             except Exception:
#                 pass

#     balances = {
#         "cash": float(register.cash_balance or 0),
#         "mkassa": float(register.mkassa_balance or 0),
#         "zadatok": float(register.zadatok_balance or 0),
#         "optima": float(register.optima_balance or 0),
#         "total": float(register.total or 0),
#     }

#     return render(request, "dds/dds_quick_op_form.html", {
#         "hotel": hotel,
#         "register": register,
#         "balances": balances,
#         "kind": kind,              # income/expense
#         "form": form,
#         "category_id": category_id,
#     })







# dds/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DDSOpCreateForm
from .models import Hotel
from .utils import user_hotels_qs


# @login_required
# def dds_op_add(request, hotel_id: int, kind: str):
#     hotels = user_hotels_qs(request.user)
#     hotel = get_object_or_404(hotels, id=hotel_id)

#     # чтобы сверху показать остатки
#     register = getattr(hotel, "cash_register", None)

#     # категория берётся из GET (выбор категории) или POST (сохранение)
#     category_id = request.GET.get("category") or request.POST.get("category") or None

#     if request.method == "POST":
#         form = DDSOpCreateForm(request.POST, kind=kind, category_id=category_id)
#         if form.is_valid():
#             op = form.save(commit=False)
#             op.hotel = hotel
#             op.created_by = request.user
#             op.save()
#             messages.success(request, "Операция сохранена.")
#             return redirect("dds:hotel_detail", hotel.id)
#         else:
#             messages.error(request, "Исправьте ошибки в форме.")
#     else:
#         form = DDSOpCreateForm(kind=kind, category_id=category_id)

#     return render(request, "dds/dds_quick_op_form.html", {
#         "hotel": hotel,
#         "register": register,
#         "kind": kind,
#         "form": form,
#         "category_id": category_id or "",
#     })



# dds/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone

from .forms import DDSOpForm
from .models import Hotel, DDSArticle, DDSOperation

from .utils import user_hotels_qs

# dds/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DDSOpCreateForm
from .models import Hotel
from .utils import user_hotels_qs

from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DDSOpCreateForm
from .models import DDSOperation, DDSArticle, CashRegister, CashMovement
from .utils import user_hotels_qs
from .cash_services import apply_cash_movement, FIELD_MAP


@login_required
def dds_op_add(request, hotel_id: int, kind: str):
    """
    kind: 'income' | 'expense'
    Создаёт DDSOperation + двигает кассу через CashMovement + CashRegister.
    Без JSON: категория выбирается через GET (перезагрузка страницы).
    """
    hotels = user_hotels_qs(request.user)
    hotel = get_object_or_404(hotels, id=hotel_id)

    register, _ = CashRegister.objects.get_or_create(hotel=hotel)

    # категория берётся из GET или POST
    category_id = request.GET.get("category") or request.POST.get("category") or None

    if request.method == "POST":
        form = DDSOpCreateForm(request.POST, kind=kind, category_id=category_id)

        if form.is_valid():
            op = form.save(commit=False)
            op.hotel = hotel
            op.created_by = request.user

            # Важно: опираемся на KIND, а не на "kind" из URL
            # (если вдруг статью выбрали не того вида — модель не даст, но на всякий)
            direction = CashMovement.IN if op.article.kind == DDSArticle.INCOME else CashMovement.OUT

            # Инкассацию специально можно не двигать через этот экран.
            # Но если вдруг ты используешь source="incasso" — оставим защиту:
            is_incasso = (op.source or "").lower() == "incasso"

            try:
                with transaction.atomic():
                    # блокируем кассу
                    register = CashRegister.objects.select_for_update().get(pk=register.pk)

                    # ✅ проверка денег при расходе (если не incasso)
                    if (not is_incasso) and direction == CashMovement.OUT:
                        field = FIELD_MAP.get(op.method)
                        if not field:
                            messages.error(request, "Неверный способ оплаты/счет.")
                            return render(request, "dds/dds_quick_op_form.html", {
                                "hotel": hotel, "register": register, "kind": kind,
                                "form": form, "category_id": category_id or "",
                            })

                        current = getattr(register, field) or Decimal("0.00")
                        if op.amount > current:
                            messages.error(
                                request,
                                f"Недостаточно средств на счете {op.get_method_display()}. Доступно: {current}"
                            )
                            return render(request, "dds/dds_quick_op_form.html", {
                                "hotel": hotel, "register": register, "kind": kind,
                                "form": form, "category_id": category_id or "",
                            })

                    # ✅ сохраняем операцию
                    op.save()

                    # ✅ двигаем кассу (если не incasso)
                    if not is_incasso:
                        # защита от дубля (на случай повторной отправки формы)
                        exists = CashMovement.objects.filter(
                            dds_operation=op,
                            account=op.method,
                            direction=direction,
                        ).exists()

                        if not exists:
                            try:
                                apply_cash_movement(
                                    hotel=hotel,
                                    account=op.method,
                                    direction=direction,
                                    amount=op.amount,
                                    created_by=request.user,
                                    happened_at=op.happened_at,
                                    comment=op.comment,
                                    dds_operation=op,
                                )
                            except IntegrityError:
                                # если constraint сработал (дубль POST) — игнор
                                pass

            except ValidationError as e:
                messages.error(request, str(e))
                return render(request, "dds/dds_quick_op_form.html", {
                    "hotel": hotel, "register": register, "kind": kind,
                    "form": form, "category_id": category_id or "",
                })

            messages.success(request, "Операция сохранена и касса обновлена.")
            return redirect("dds:hotel_detail", hotel.id)

        else:
            messages.error(request, "Исправьте ошибки в форме.")
    else:
        form = DDSOpCreateForm(kind=kind, category_id=category_id)

    return render(request, "dds/dds_quick_op_form.html", {
        "hotel": hotel,
        "register": register,
        "kind": kind,
        "form": form,
        "category_id": category_id or "",
    })

# @login_required
# def dds_op_add(request, hotel_id: int, kind: str):
#     hotels = user_hotels_qs(request.user)
#     hotel = get_object_or_404(hotels, id=hotel_id)

#     # чтобы сверху показать остатки
#     register = getattr(hotel, "cash_register", None)

#     # категория берётся из GET (выбор категории) или POST (сохранение)
#     category_id = request.GET.get("category") or request.POST.get("category") or None

#     if request.method == "POST":
#         form = DDSOpCreateForm(request.POST, kind=kind, category_id=category_id)
#         if form.is_valid():
#             op = form.save(commit=False)
#             op.hotel = hotel
#             op.created_by = request.user
#             op.save()
#             messages.success(request, "Операция сохранена.")
#             return redirect("dds:hotel_detail", hotel.id)
#         else:
#             messages.error(request, "Исправьте ошибки в форме.")
#     else:
#         form = DDSOpCreateForm(kind=kind, category_id=category_id)

#     return render(request, "dds/dds_quick_op_form.html", {
#         "hotel": hotel,
#         "register": register,
#         "kind": kind,
#         "form": form,
#         "category_id": category_id or "",
#     })

# @login_required
# def dds_op_add(request, hotel_id: int, kind: str):
#     hotels = user_hotels_qs(request.user)
#     hotel = get_object_or_404(hotels, id=hotel_id)

#     # category_id берём из GET или POST
#     category_id = request.POST.get("category") or request.GET.get("category") or None

#     if request.method == "POST":
#         form = DDSOpForm(request.POST, kind=kind, category_id=category_id)
#         if form.is_valid():
#             op = form.save(commit=False)
#             op.hotel = hotel
#             op.created_by = request.user
#             if not op.happened_at:
#                 op.happened_at = timezone.now()
#             op.save()
#             return redirect("dds:hotel_detail", hotel.id)
#     else:
#         form = DDSOpForm(kind=kind, category_id=category_id)
#         if category_id:
#             try:
#                 form.fields["category"].initial = int(category_id)
#             except Exception:
#                 pass

#     return render(request, "dds/dds_quick_op_form.html", {
#         "hotel": hotel,
#         "kind": kind,
#         "form": form,
#     })


@login_required
def dds_articles_json(request):
    """
    /dds/articles/?kind=income&category=123
    Возвращает статьи только выбранной категории (строго).
    """
    kind = request.GET.get("kind") or ""
    category_id = request.GET.get("category") or ""

    qs = DDSArticle.objects.filter(is_active=True, kind=kind)

    if category_id:
        try:
            qs = qs.filter(category_id=int(category_id))
        except Exception:
            pass
    else:
        # если категорию не выбрали — можно вернуть пусто, чтобы заставить выбирать категорию
        qs = qs.none()

    return JsonResponse({
        "results": [{"id": a.id, "name": a.name} for a in qs.order_by("name")]
    })
