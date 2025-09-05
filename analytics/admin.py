from django.contrib import admin
from .models import Dataset

@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ['name', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['name']
    readonly_fields = ['uploaded_at']