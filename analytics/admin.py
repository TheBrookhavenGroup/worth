from django.contrib import admin
from .models import PPMResult


@admin.register(PPMResult)
class PPMResultAdmin(admin.ModelAdmin):
    list_display = ('dt', 'formatted_total')
    ordering = ('-dt', )

    def formatted_total(self, obj):
        return f"{obj.total/1.e6:.3f}M"
