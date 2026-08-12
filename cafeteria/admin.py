from django.contrib import admin

from .models import (
    CafeteriaMenu,
    CafeteriaReservation,
    CafeteriaReservationItem,
    CafeteriaWeek,
)


class CafeteriaMenuInline(admin.TabularInline):
    model = CafeteriaMenu
    extra = 5
    max_num = 5

    fields = (
        "day",
        "food_name",
        "description",
        "price",
        "confirmed_count_display",
    )

    readonly_fields = (
        "confirmed_count_display",
    )

    @admin.display(description="تعداد رزرو قطعی")
    def confirmed_count_display(self, obj):

        if not obj or not obj.pk:
            return 0

        return obj.confirmed_count


@admin.register(CafeteriaWeek)
class CafeteriaWeekAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "start_date",
        "is_active",
        "confirmed_revenue_display",
    )

    list_filter = (
        "is_active",
    )

    inlines = [
        CafeteriaMenuInline,
    ]


    @admin.display(description="مجموع دریافتی قطعی")
    def confirmed_revenue_display(self, obj):
        return f"{obj.confirmed_revenue:,} تومان"

class CafeteriaReservationItemInline(admin.TabularInline):
    model = CafeteriaReservationItem
    extra = 0

    fields = (
        "menu",
        "wants_food",
    )


@admin.register(CafeteriaReservation)
class CafeteriaReservationAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "week",
        "payment_method",
        "payment_status",
        "total_price_display",
        "created_at",
    )

    list_filter = (
        "week",
        "payment_method",
        "payment_status",
    )

    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
    )

    inlines = [
        CafeteriaReservationItemInline,
    ]

    @admin.display(description="مبلغ کل")
    def total_price_display(self, obj):
        return f"{obj.total_price:,} تومان"



    @admin.action(description="تأیید پرداخت انتخاب‌شده‌ها")
    def approve_payment(self, request, queryset):
        queryset.update(
            payment_status="paid",
        )


    @admin.action(description="رد فیش انتخاب‌شده‌ها")
    def reject_payment(self, request, queryset):
        queryset.update(
            payment_status="rejected",
        )

    actions = [
        "approve_payment",
        "reject_payment",
    ]