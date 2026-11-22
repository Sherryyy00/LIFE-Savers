from django.contrib import admin, messages

from .matching import create_notifications, find_matching_donors
from .models import BloodRequest, DonorResponse, InvalidTransition


class DonorResponseInline(admin.TabularInline):
    model = DonorResponse
    extra = 0
    fields = ["donor", "status", "distance_km", "notified_at", "responded_at"]
    readonly_fields = ["distance_km", "notified_at", "responded_at"]
    autocomplete_fields = ["donor"]


@admin.register(BloodRequest)
class BloodRequestAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "blood_group",
        "units_needed",
        "hospital_name",
        "urgency",
        "needed_by",
        "status",
        "created_at",
    ]
    list_filter = ["status", "urgency", "blood_group", "city"]
    search_fields = [
        "reference",
        "patient_label",
        "hospital__name",
        "hospital_other",
        "requested_by__full_name",
        "requested_by__phone",
    ]
    autocomplete_fields = ["requested_by", "hospital"]
    readonly_fields = ["reference", "reviewed_by", "reviewed_at", "closed_at", "created_at", "updated_at"]
    date_hierarchy = "needed_by"
    inlines = [DonorResponseInline]
    actions = ["approve_and_match", "mark_fulfilled"]
    list_select_related = ["hospital", "city"]

    @admin.action(description="Approve and notify matching donors")
    def approve_and_match(self, request, queryset):
        for br in queryset:
            try:
                if br.status == BloodRequest.Status.PENDING_REVIEW:
                    br.approve(request.user)
                matches = find_matching_donors(br)
                create_notifications(br, matches)
                self.message_user(request, f"{br.reference}: {len(matches)} donor(s) matched.")
            except (InvalidTransition, ValueError) as exc:
                self.message_user(request, f"{br.reference}: {exc}", level=messages.WARNING)

    @admin.action(description="Mark as fulfilled")
    def mark_fulfilled(self, request, queryset):
        for br in queryset:
            try:
                br.mark_fulfilled()
            except InvalidTransition as exc:
                self.message_user(request, f"{br.reference}: {exc}", level=messages.WARNING)


@admin.register(DonorResponse)
class DonorResponseAdmin(admin.ModelAdmin):
    list_display = ["blood_request", "donor", "status", "distance_km", "notified_at", "responded_at"]
    list_filter = ["status"]
    search_fields = ["blood_request__reference", "donor__user__full_name"]
    autocomplete_fields = ["blood_request", "donor"]
