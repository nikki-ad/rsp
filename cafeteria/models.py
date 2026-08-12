from django.db import models

from core.models import BaseModel


class CafeteriaWeek(BaseModel):

    title = models.CharField(
        max_length=100,
        verbose_name="عنوان هفته",
    )

    start_date = models.DateField(
        unique=True,
        verbose_name="تاریخ شروع هفته",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    class Meta:
        verbose_name = "هفته غذایی"
        verbose_name_plural = "هفته‌های غذایی"
        ordering = (
            "-start_date",
        )

    @property
    def confirmed_revenue(self):
        return sum(
            reservation.final_amount
            for reservation in self.reservations.filter(
                payment_status="paid",
            )
        )

    def __str__(self):
        return self.title


class CafeteriaMenu(BaseModel):

    DAY_CHOICES = (
        ("saturday", "شنبه"),
        ("sunday", "یکشنبه"),
        ("monday", "دوشنبه"),
        ("tuesday", "سه‌شنبه"),
        ("wednesday", "چهارشنبه"),
    )

    week = models.ForeignKey(
        CafeteriaWeek,
        on_delete=models.CASCADE,
        related_name="menus",
        null=True,
        blank=True,
        verbose_name="هفته غذایی",
    )

    day = models.CharField(
        max_length=20,
        choices=DAY_CHOICES,
        null=True,
        blank=True,
        verbose_name="روز هفته",
    )

    food_name = models.CharField(
        max_length=200,
        verbose_name="نام غذا",
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="توضیحات",
    )

    price = models.PositiveIntegerField(
        default=0,
        verbose_name="قیمت",
    )

    class Meta:
        verbose_name = "غذای روز"
        verbose_name_plural = "غذاهای هفته"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "week",
                    "day",
                ],
                name="unique_cafeteria_week_day",
            )
        ]


    @property
    def confirmed_count(self):
        return self.reservation_items.filter(
            wants_food=True,
            reservation__payment_status="paid",
        ).count()

    def __str__(self):
        return f"{self.week} - {self.get_day_display()} - {self.food_name}"



class CafeteriaReservation(BaseModel):

    student = models.ForeignKey(
        "accounts.StudentProfile",
        on_delete=models.CASCADE,
        related_name="cafeteria_reservations",
        verbose_name="دانش‌آموز",
    )

    week = models.ForeignKey(
        CafeteriaWeek,
        on_delete=models.CASCADE,
        related_name="reservations",
        null=True,
        blank=True,
        verbose_name="هفته غذایی",
    )

    PAYMENT_METHOD_CHOICES = (
        ("zarinpal", "درگاه زرین‌پال"),
        ("receipt", "فیش واریزی"),
    )

    PAYMENT_STATUS_CHOICES = (
        ("pending", "پرداخت نشده"),
        ("receipt_pending", "در انتظار بررسی فیش"),
        ("paid", "پرداخت تأیید شده"),
        ("rejected", "فیش رد شده"),
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
        null=True,
        verbose_name="روش پرداخت",
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending",
        verbose_name="وضعیت پرداخت",
    )

    receipt_image = models.ImageField(
        upload_to="cafeteria_receipts/",
        blank=True,
        null=True,
        verbose_name="تصویر فیش واریزی",
    )

    zarinpal_authority = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Authority زرین‌پال",
    )

    zarinpal_ref_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="کد پیگیری زرین‌پال",
    )

    final_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="مبلغ نهایی رزرو",
    )

    class Meta:
        verbose_name = "رزرو هفتگی غذا"
        verbose_name_plural = "رزروهای هفتگی غذا"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "week",
                ],
                name="unique_student_week_reservation",
            )
        ]


    @property
    def total_price(self):
        return sum(
            item.menu.price
            for item in self.items.select_related("menu").all()
            if item.wants_food
        )
    
    @property
    def is_confirmed(self):
        return self.payment_status == "paid"
    
    def __str__(self):
        return f"{self.student} - {self.week}"


class CafeteriaReservationItem(BaseModel):

    reservation = models.ForeignKey(
        CafeteriaReservation,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="رزرو هفتگی",
    )

    menu = models.ForeignKey(
        CafeteriaMenu,
        on_delete=models.CASCADE,
        related_name="reservation_items",
        verbose_name="غذای روز",
    )

    wants_food = models.BooleanField(
        default=False,
        verbose_name="غذا می‌خواهد",
    )

    class Meta:
        verbose_name = "انتخاب غذای روز"
        verbose_name_plural = "انتخاب‌های غذای روز"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "reservation",
                    "menu",
                ],
                name="unique_reservation_menu_item",
            )
        ]

    def __str__(self):
        return f"{self.reservation} - {self.menu}"