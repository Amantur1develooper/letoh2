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


# dds/services_cash.py (или pms/services.py, где тебе удобно)

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from dds.models import CashRegister, CashMovement, CashTransfer

ACCOUNT_TO_FIELD = {
    CashMovement.ACC_CASH: "cash_balance",
    CashMovement.ACC_MKASSA: "mkassa_balance",
    CashMovement.ACC_ZADATOK: "zadatok_balance",
    CashMovement.ACC_OPTIMA: "optima_balance",
}

class CashTransferError(Exception):
    pass


@transaction.atomic
def transfer_between_accounts(*, hotel, from_account: str, to_account: str, amount: Decimal, user, happened_at=None, comment="") -> CashTransfer:
    if from_account == to_account:
        raise CashTransferError("Нельзя переводить на тот же самый счет.")
    if not amount or amount <= 0:
        raise CashTransferError("Сумма должна быть больше 0.")

    happened_at = happened_at or timezone.now()

    register = CashRegister.objects.select_for_update().get(hotel=hotel)

    from_field = ACCOUNT_TO_FIELD.get(from_account)
    to_field = ACCOUNT_TO_FIELD.get(to_account)
    if not from_field or not to_field:
        raise CashTransferError("Неверный счет.")

    from_balance = getattr(register, from_field) or Decimal("0")
    if from_balance < amount:
        raise CashTransferError(f"Недостаточно средств на счете '{from_account}'. Баланс: {from_balance}")

    # обновляем балансы кассы
    setattr(register, from_field, from_balance - amount)
    setattr(register, to_field, (getattr(register, to_field) or Decimal("0")) + amount)
    register.save(update_fields=[from_field, to_field, "updated_at"])

    transfer = CashTransfer.objects.create(
        hotel=hotel,
        register=register,
        from_account=from_account,
        to_account=to_account,
        amount=amount,
        happened_at=happened_at,
        comment=comment,
        created_by=user,
    )

    # движение OUT
    CashMovement.objects.create(
        register=register,
        hotel=hotel,
        direction=CashMovement.OUT,
        account=from_account,
        amount=amount,
        happened_at=happened_at,
        comment=f"Перевод на {to_account}. {comment}".strip(),
        transfer=transfer,
        created_by=user,
    )

    # движение IN
    CashMovement.objects.create(
        register=register,
        hotel=hotel,
        direction=CashMovement.IN,
        account=to_account,
        amount=amount,
        happened_at=happened_at,
        comment=f"Перевод с {from_account}. {comment}".strip(),
        transfer=transfer,
        created_by=user,
    )

    return transfer
