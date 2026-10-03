from django.contrib import admin
from django.db import models
from django.core.exceptions import FieldDoesNotExist

from .jalali import JalaliDateField, JalaliDateTimeField, jalali_format


class JalaliAdminMixin:
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, models.DateTimeField):
            kwargs.update(form_class=JalaliDateTimeField, widget=JalaliDateTimeField.widget)
        elif isinstance(db_field, models.DateField):
            kwargs.update(form_class=JalaliDateField, widget=JalaliDateField.widget)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def _date_display(self, name):
        try:
            field = self.model._meta.get_field(name)
        except (FieldDoesNotExist, TypeError):
            return None
        if not isinstance(field, models.DateField):
            return None

        @admin.display(description=field.verbose_name, ordering=name)
        def display(obj):
            return jalali_format(getattr(obj, name), isinstance(field, models.DateTimeField))
        return display

    def get_list_display(self, request):
        return [self._date_display(name) or name for name in super().get_list_display(request)]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        for name in fields:
            display = self._date_display(name)
            if display:
                setattr(self, "jalali_" + name, display)
        return tuple("jalali_" + name if isinstance(name, str) and self._date_display(name) else name for name in fields)

    def get_fieldsets(self, request, obj=None):
        readonly = self.get_readonly_fields(request, obj)

        def replace(value):
            if isinstance(value, str):
                return "jalali_" + value if "jalali_" + value in readonly else value
            return tuple(replace(item) for item in value)

        return [(label, {**options, "fields": replace(options["fields"])})
                for label, options in super().get_fieldsets(request, obj)]
