from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction

from django.utils import timezone

from .models import CashRegister, CashMovement, CashTransfer, Hotel

FIELD_MAP = {
    CashMovement.ACC_CASH: "cash_balance",
    CashMovement.ACC_MKASSA: "mkassa_balance",
    CashMovement.ACC_ZADATOK: "zadatok_balance",
    CashMovement.ACC_OPTIMA: "optima_balance",
}


class CashTransferError(Exception):
    pass


def _to_decimal(x) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        raise ValidationError("Некорректная сумма.")


@transaction.atomic
def apply_cash_movement(
    *,
    hotel: Hotel,
    account: str,
    direction: str,
    amount,
    created_by,
    happened_at=None,
    comment="",
    dds_operation=None,
    incasso=None,
    transfer=None,
):
    """
    Создаёт CashMovement и обновляет CashRegister.
    ВАЖНО: обновляем через объект reg (а не через .update(F())),
    чтобы обновлялся updated_at и не было “визуально не меняется”.
    """
    happened_at = happened_at or timezone.now()
    amount = _to_decimal(amount)

    if amount <= 0:
        raise ValidationError("Сумма должна быть больше 0.")

    field = FIELD_MAP.get(account)
    if not field:
        raise ValidationError(f"Неизвестный счет: {account}")

    # берём/создаём кассу
    reg, _ = CashRegister.objects.get_or_create(hotel=hotel)
    reg = CashRegister.objects.select_for_update().get(pk=reg.pk)

    current = getattr(reg, field) or Decimal("0.00")

    # расчёт нового баланса
    if direction == CashMovement.IN:
        new_value = current + amount
    elif direction == CashMovement.OUT:
        if amount > current:
            raise ValidationError(f"Недостаточно средств на счете {account}. Доступно: {current}")
        new_value = current - amount
    else:
        raise ValidationError("Неверное направление движения.")

    # ✅ создаём движение
    move = CashMovement.objects.create(
        register=reg,
        hotel=hotel,
        account=account,
        direction=direction,
        amount=amount,
        happened_at=happened_at,
        comment=comment or "",
        created_by=created_by,
        dds_operation=dds_operation,
        incasso=incasso,
        transfer=transfer,
    )

    # ✅ обновляем баланс + updated_at
    setattr(reg, field, new_value)
    reg.save(update_fields=[field, "updated_at"])

    return move


@transaction.atomic
def transfer_between_accounts(
    *,
    hotel: Hotel,
    from_account: str,
    to_account: str,
    amount,
    user,
    happened_at=None,
    comment="",
) -> CashTransfer:
    """
    Внутренний перевод между счетами одного отеля:
    OPTIMA -> CASH, MKASSA -> OPTIMA и т.д.
    Создаёт CashTransfer + 2 CashMovement (OUT/IN) и обновляет кассу.
    """
    happened_at = happened_at or timezone.now()
    amount = _to_decimal(amount)

    if from_account == to_account:
        raise CashTransferError("Нельзя переводить на тот же самый счет.")
    if amount <= 0:
        raise CashTransferError("Сумма должна быть больше 0.")

    # касса под блокировкой
    reg, _ = CashRegister.objects.get_or_create(hotel=hotel)
    reg = CashRegister.objects.select_for_update().get(pk=reg.pk)

    from_field = FIELD_MAP.get(from_account)
    to_field = FIELD_MAP.get(to_account)
    if not from_field or not to_field:
        raise CashTransferError("Неверный счет.")

    from_balance = getattr(reg, from_field) or Decimal("0.00")
    if from_balance < amount:
        raise CashTransferError(
            f"Недостаточно средств на счете '{from_account}'. Баланс: {from_balance}"
        )

    # создаём перевод
    transfer = CashTransfer.objects.create(
        hotel=hotel,
        register=reg,
        from_account=from_account,
        to_account=to_account,
        amount=amount,
        happened_at=happened_at,
        comment=comment or "",
        created_by=user,
    )

    # ✅ делаем 2 движения через общий сервис (и касса обновится корректно)
    apply_cash_movement(
        hotel=hotel,
        account=from_account,
        direction=CashMovement.OUT,
        amount=amount,
        created_by=user,
        happened_at=happened_at,
        comment=f"Перевод на {to_account}. {comment}".strip(),
        transfer=transfer,
    )

    apply_cash_movement(
        hotel=hotel,
        account=to_account,
        direction=CashMovement.IN,
        amount=amount,
        created_by=user,
        happened_at=happened_at,
        comment=f"Перевод с {from_account}. {comment}".strip(),
        transfer=transfer,
    )

    return transfer
