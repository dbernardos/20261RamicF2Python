from django.contrib import admin

from .models import VibrationCollection

@admin.register(VibrationCollection)
class VibrationCollectionAdmin(admin.ModelAdmin):
    list_display = ('motor_id', 'collected_at', 'status',)
    list_display_links = ('motor_id',)
    search_fields = ('motor_id',)
    list_filter = ('status',)
    list_editable = ('status',)