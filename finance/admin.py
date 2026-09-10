from django.contrib import admin
from .models import Transaction, PortfolioItem, Preferences

admin.site.register([Transaction, PortfolioItem, Preferences])
