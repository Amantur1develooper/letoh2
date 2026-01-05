from django.urls import path
from . import views

app_name = "dds"

urlpatterns = [
    path("", views.dds_dashboard, name="dds_dashboard"),
    path("list/", views.dds_list, name="dds_list"),
    path("create/", views.dds_create, name="dds_create"),
    path("void/<int:pk>/", views.dds_void, name="dds_void"),
    path("articles/", views.dds_articles, name="dds_articles"),
    
    path("hotels/", views.hotel_catalog, name="hotel_catalog"),
    path("hotels2/", views.hotel_list, name="hotel_list"),
    path("hotels/<int:pk>/", views.hotel_detail, name="hotel_detail"),

    path("hotels/<int:pk>/export/excel/", views.hotel_detail_export_excel, name="hotel_export_excel"),
    path("report/export/excel/", views.unified_report_export_excel, name="unified_report_excel"),

    path("report/", views.unified_report, name="unified_report"),

    path("hotels/<int:pk>/incasso/", views.incasso_create, name="incasso_create"),
    path("accounting/", views.accounting, name="accounting"),
    path("accounting/export/excel/", views.accounting_export_excel, name="accounting_excel"),

]
