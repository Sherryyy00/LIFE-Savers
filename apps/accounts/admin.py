from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import User


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("phone", "full_name", "email")


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreateForm
    ordering = ["-date_joined"]
    list_display = ["full_name", "phone", "role", "is_phone_verified", "is_active", "date_joined"]
    list_filter = ["role", "is_active", "is_staff", "preferred_language"]
    search_fields = ["full_name", "phone", "email"]
    readonly_fields = ["date_joined", "last_login"]

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        (_("Profile"), {"fields": ("full_name", "email", "preferred_language", "phone_verified_at")}),
        (_("Role"), {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "full_name", "email", "password1", "password2")}),
    )

    @admin.display(boolean=True, description="Phone verified")
    def is_phone_verified(self, obj):
        return obj.is_phone_verified
