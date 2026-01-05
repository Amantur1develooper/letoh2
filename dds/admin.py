from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import DDSCategory, Hotel, DDSArticle, DDSOperation, CashMovement, CashRegister

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)

@admin.register(DDSArticle)
class DDSArticleAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "name", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name",)
admin.site.register(CashMovement)
admin.site.register(CashRegister)
admin.site.register(DDSCategory)
@admin.register(DDSOperation)
class DDSOperationAdmin(admin.ModelAdmin):
    list_display = ("id", "hotel", "article", "amount", "happened_at", "method", "is_voided")
    list_filter = ("hotel", "article__kind", "method", "is_voided")
    search_fields = ("counterparty", "comment", "source")
