from django.contrib import admin

from .models import Donation, DonorProfile


class DonationInline(admin.TabularInline):
    model = Donation
    extra = 0
    fields = ["donated_on", "hospital", "blood_request", "units", "verified_at"]
    readonly_fields = ["verified_at"]
    autocomplete_fields = ["hospital", "blood_request"]


@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "blood_group",
        "blood_group_verified",
        "city",
        "area",
        "is_available",
        "last_donation_date",
        "eligible_now",
    ]
    list_filter = ["blood_group", "blood_group_verified", "is_available", "city"]
    search_fields = ["user__full_name", "user__phone"]
    autocomplete_fields = ["user", "area"]
    readonly_fields = [
        "last_donation_date",
        "consent_given_at",
        "privacy_policy_version",
        "eligibility_confirmed_at",
        "created_at",
        "updated_at",
    ]
    inlines = [DonationInline]
    list_select_related = ["user", "city", "area"]

    @admin.display(boolean=True, description="Eligible now")
    def eligible_now(self, obj):
        return obj.is_eligible()


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ["donor", "donated_on", "hospital", "blood_request", "units", "is_verified"]
    list_filter = ["donated_on", "hospital"]
    search_fields = ["donor__user__full_name", "donor__user__phone", "blood_request__reference"]
    autocomplete_fields = ["donor", "hospital", "blood_request"]
    readonly_fields = ["verified_by", "verified_at"]
    actions = ["verify"]

    @admin.display(boolean=True, description="Verified")
    def is_verified(self, obj):
        return obj.verified_at is not None

    @admin.action(description="Verify selected donations")
    def verify(self, request, queryset):
        count = 0
        for donation in queryset.filter(verified_at__isnull=True).select_related("donor"):
            donation.verify(request.user)
            count += 1
        self.message_user(request, f"{count} donation(s) verified.")
