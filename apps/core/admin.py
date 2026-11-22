from django.contrib import admin

from .models import Area, City, Hospital


class AreaInline(admin.TabularInline):
    model = Area
    extra = 0
    fields = ["name", "name_ur", "latitude", "longitude"]


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name", "name_ur", "is_active", "latitude", "longitude"]
    list_filter = ["is_active"]
    search_fields = ["name", "name_ur"]
    inlines = [AreaInline]


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "latitude", "longitude"]
    list_filter = ["city"]
    search_fields = ["name", "name_ur"]


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "has_blood_bank", "is_verified", "phone"]
    list_filter = ["city", "has_blood_bank", "is_verified"]
    search_fields = ["name", "address"]
    actions = ["mark_verified"]

    @admin.action(description="Mark selected hospitals as verified")
    def mark_verified(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} hospital(s) verified.")
