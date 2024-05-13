from django.contrib import admin
from .models import PPMResult


@admin.register(PPMResult)
class PPMResultAdmin(admin.ModelAdmin):
    list_display = ('d', 'total')
    ordering = ('-d', )

    def total(self, obj):
        return f"{obj.value / 1.e6:.3f}M"
