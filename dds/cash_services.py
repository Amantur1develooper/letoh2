from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import CashRegister, CashMovement, Hotel

FIELD_MAP = {
    CashMovement.ACC_CASH: "cash_balance",
    CashMovement.ACC_MKASSA: "mkassa_balance",
    CashMovement.ACC_ZADATOK: "zadatok_balance",
    CashMovement.ACC_OPTIMA: "optima_balance",
}

@transaction.atomic
def apply_cash_movement(
    *, hotel: Hotel, account: str, direction: str, amount,
    created_by, happened_at=None, comment="", dds_operation=None, incasso=None
):
    if happened_at is None:
        happened_at = timezone.now()

    amount = Decimal(amount)

    field = FIELD_MAP.get(account)
    if not field:
        raise ValidationError(f"Неизвестный счет: {account}")

    reg, _ = CashRegister.objects.get_or_create(hotel=hotel)
    reg = CashRegister.objects.select_for_update().get(pk=reg.pk)

    current = getattr(reg, field) or Decimal("0.00")

    # ✅ нельзя уйти в минус
    if direction == CashMovement.OUT and amount > current:
        raise ValidationError(f"Недостаточно средств на счете {account}. Доступно: {current}")

    # ✅ создаём движение
    move = CashMovement.objects.create(
        register=reg,
        hotel=hotel,
        account=account,
        direction=direction,
        amount=amount,
        happened_at=happened_at,
        comment=comment,
        created_by=created_by,
        dds_operation=dds_operation,
        incasso=incasso,
    )

    # ✅ обновляем нужный баланс
    CashRegister.objects.filter(pk=reg.pk).update(**{
        field: F(field) + move.signed_amount
    })

    return move
