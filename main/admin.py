from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from main.models import SSOIdentity, User


class WearBackUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')


class WearBackUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class WearBackUserAdmin(UserAdmin):
    add_form = WearBackUserCreationForm
    form = WearBackUserChangeForm
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'is_active')
    add_fieldsets = UserAdmin.add_fieldsets + (('Profile', {'fields': ('email', 'first_name', 'last_name')}),)


@admin.register(SSOIdentity)
class SSOIdentityAdmin(admin.ModelAdmin):
    list_display = ('provider', 'subject', 'user', 'created_at')
    readonly_fields = ('provider', 'subject', 'user', 'created_at')

    def has_add_permission(self, request):
        return False
