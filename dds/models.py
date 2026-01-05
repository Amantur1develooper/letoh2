from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from django.db import models


class Hotel(models.Model):
    """
    Если у тебя уже есть Branch/Hotel в другом приложении —
    удали этот класс и замени FK ниже на свою модель.
    """
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Отель"
        verbose_name_plural = "Отели"
        ordering = ["name"]
        
    def __str__(self):
        return self.name


class DDSCategory(models.Model):
    INCOME = "income"
    EXPENSE = "expense"
    KIND_CHOICES = (
        (INCOME, "Доход"),
        (EXPENSE, "Расход"),
    )

    kind = models.CharField(max_length=10, choices=KIND_CHOICES, verbose_name="Вид")
    name = models.CharField(max_length=120, verbose_name="Категория")
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская категория",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Категория ДДС"
        verbose_name_plural = "Категории ДДС"
        ordering = ["kind", "parent_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "parent", "name"],
                name="uniq_dds_category_kind_parent_name",
            )
        ]

    def __str__(self):
        if self.parent:
            return f"{self.get_kind_display()}: {self.parent.name} → {self.name}"
        return f"{self.get_kind_display()}: {self.name}"

class DDSArticle(models.Model):
    INCOME = "income"
    EXPENSE = "expense"
    KIND_CHOICES = (
        (INCOME, "Доход"),
        (EXPENSE, "Расход"),
    )

    kind = models.CharField(max_length=10, choices=KIND_CHOICES, verbose_name="Вид")
    category = models.ForeignKey(
        "DDSCategory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="articles",
        verbose_name="Категория",
    )
    name = models.CharField(max_length=120, verbose_name="имя")
    is_active = models.BooleanField(default=True, verbose_name="активно?")

    class Meta:
        verbose_name = "Статья ДДС"
        verbose_name_plural = "Статьи ДДС"
        ordering = ["kind", "category_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "category", "name"],
                name="uniq_dds_article_kind_cat_name",
            )
        ]

    def __str__(self):
        if self.category:
            return f"Категории {self.get_kind_display()}: — {self.name}"
        return f"{self.get_kind_display()}: {self.name}"



class DDSOperation(models.Model):
    CASH = "cash"
    MKASSA = "mkassa"
    ZADATOK = "zadatok"
    OPTIMA = "optima"
   
    
    METHOD_CHOICES = (
        (CASH, "Наличные"),
        (MKASSA, "Mkassa"),
        (ZADATOK, "Задаток"),
        (OPTIMA, "Оптима"),
    )

    hotel = models.ForeignKey(Hotel, on_delete=models.PROTECT, related_name="dds_ops", verbose_name="отель")
    article = models.ForeignKey(DDSArticle, on_delete=models.PROTECT, related_name="ops", verbose_name="статья")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="сумма")  # всегда положительная
    happened_at = models.DateTimeField(default=timezone.now, verbose_name="дата")
    method = models.CharField(max_length=12, choices=METHOD_CHOICES, default=CASH, verbose_name="способ оплаты")
    counterparty = models.CharField(max_length=180, blank=True, verbose_name="поставщик/гость/компания")  # поставщик/гость/компания
    comment = models.TextField(blank=True, verbose_name="комментарии")

    # связь с источником (касса/документ) - пока строкой, потом можно расширить
    source = models.CharField(max_length=120, blank=True, verbose_name='источник')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dds_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # вместо удаления — сторно
    is_voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dds_voided",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Операция ДДС"
        verbose_name_plural = "Операции ДДС"
        ordering = ["-happened_at", "-id"]
        indexes = [
            models.Index(fields=["hotel", "happened_at"]),
            models.Index(fields=["article", "happened_at"]),
        ]

    @property
    def kind(self) -> str:
        return self.article.kind  # income/expense

    def void(self, user, reason: str):
        self.is_voided = True
        self.void_reason = reason[:255]
        self.voided_at = timezone.now()
        self.voided_by = user
        self.save(update_fields=["is_voided", "void_reason", "voided_at", "voided_by"])

    def __str__(self):
        return f"{self.hotel} {self.article} {self.amount}"


class CashIncasso(models.Model):
    CASH = "cash"
    MKASSA = "mkassa"
    ZADATOK = "zadatok"
    OPTIMA = "optima"

    METHOD_CHOICES = (
        (CASH, "Наличные"),
        (MKASSA, "Mkassa"),
        (ZADATOK, "Задаток"),
        (OPTIMA, "Оптима"),
    )

    hotel = models.ForeignKey(Hotel, on_delete=models.PROTECT, related_name="incassos", verbose_name="отель")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="сумма")
    happened_at = models.DateTimeField(default=timezone.now, verbose_name="дата")
    method = models.CharField(max_length=12, choices=METHOD_CHOICES, default=CASH, verbose_name="с какого счета")
    comment = models.TextField(blank=True, verbose_name="комментарий")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="incasso_created", verbose_name="создал"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Инкассация"
        verbose_name_plural = "Инкассации"
        ordering = ["-happened_at", "-id"]

    def __str__(self):
        return f"Инкассация {self.hotel} {self.amount}"


class CashRegister(models.Model):
    hotel = models.OneToOneField(Hotel, on_delete=models.CASCADE, related_name="cash_register", verbose_name="отель")

    # НАЛ
    cash_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Наличные (касса)")

    # БЕЗНАЛ
    mkassa_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Mkassa")
    zadatok_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Задаток")
    optima_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Оптима")

    updated_at = models.DateTimeField(auto_now=True)

    @property
    def noncash_total(self):
        return (self.mkassa_balance or 0) + (self.zadatok_balance or 0) + (self.optima_balance or 0)

    @property
    def total(self):
        return (self.cash_balance or 0) + self.noncash_total
    
    class Meta:
        verbose_name = "Касса"
        verbose_name_plural = "Кассы"
        ordering = ["hotel__name"]
        
    def __str__(self):
        return f"Касса {self.hotel.name} | нал={self.cash_balance} | безнал={self.noncash_total}"


class CashMovement(models.Model):
    IN = "in"
    OUT = "out"
    DIR_CHOICES = (
        (IN, "Приход"),
        (OUT, "Расход/Списание"),
    )

    ACC_CASH = "cash"
    ACC_MKASSA = "mkassa"
    ACC_ZADATOK = "zadatok"
    ACC_OPTIMA = "optima"
    ACCOUNT_CHOICES = (
        (ACC_CASH, "Наличные"),
        (ACC_MKASSA, "Mkassa"),
        (ACC_ZADATOK, "Задаток"),
        (ACC_OPTIMA, "Оптима"),
    )

    register = models.ForeignKey(CashRegister, on_delete=models.PROTECT, related_name="movements")
    hotel = models.ForeignKey(Hotel, on_delete=models.PROTECT, related_name="cash_movements")

    direction = models.CharField(max_length=3, choices=DIR_CHOICES)
    account = models.CharField(max_length=10, choices=ACCOUNT_CHOICES)  # куда влияет

    amount = models.DecimalField(max_digits=12, decimal_places=2)  # всегда +
    happened_at = models.DateTimeField(default=timezone.now)
    comment = models.TextField(blank=True)

    # можно FK, чтобы делать сторно/реверс
    dds_operation = models.ForeignKey(
        DDSOperation, on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_moves"
    )
    incasso = models.ForeignKey(
        "CashIncasso", on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_moves"
    )

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_moves_created")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def signed_amount(self):
        return self.amount if self.direction == self.IN else -self.amount

    class Meta:
        verbose_name = "Движение денег"
        verbose_name_plural = "Движения денег"
        ordering = ["-happened_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["dds_operation", "account", "direction"],
                name="uniq_cashmove_dds_account_dir",
                condition=Q(dds_operation__isnull=False),
            )
        ]