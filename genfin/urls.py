from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path
from finance import views
from finance import open_finance_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("login/", views.GenFinLoginView.as_view(), name="login"),
    path("register/", views.register, name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("demo/", views.demo, name="demo"),
    path("landing/", views.landing, name="landing"),
    path("transactions/", views.transactions, name="transactions"),
    path("profile/", views.profile, name="profile"),
    path("profile/reset/", views.account_reset, name="account_reset"),
    path("open-finance/", open_finance_views.index, name="open_finance"),
    path("api/open-finance/token/", open_finance_views.connect_token, name="pluggy_token"),
    path("api/open-finance/items/", open_finance_views.register_item, name="pluggy_register"),
    path("api/open-finance/status/", open_finance_views.status, name="pluggy_status"),
    path("api/open-finance/<int:pk>/sync/", open_finance_views.sync, name="pluggy_sync"),
    path(
        "api/open-finance/<int:pk>/disconnect/",
        open_finance_views.disconnect,
        name="pluggy_disconnect",
    ),
    path("design-system/", views.design_system, name="design_system"),
    path("api/transactions/", views.transaction_save, name="transaction_create"),
    path("api/transactions/<int:pk>/", views.transaction_detail),
    path("api/transactions/<int:pk>/save/", views.transaction_save),
    path("api/transactions/<int:pk>/delete/", views.transaction_delete),
    path("api/portfolio/", views.portfolio_save),
    path("api/portfolio/<int:pk>/", views.portfolio_detail),
    path("api/portfolio/<int:pk>/save/", views.portfolio_save),
    path("api/portfolio/<int:pk>/delete/", views.portfolio_delete),
    path("api/preferences/", views.preferences),
    path("export/transactions/", views.export_transactions, name="export_transactions"),
]
for kind in views.PAGE_CONFIG:
    urlpatterns.append(
        path(f"{kind.replace('_', '-')}/", views.portfolio, {"kind": kind}, name=kind)
    )
