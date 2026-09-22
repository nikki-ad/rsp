from datetime import date

from django.test import TestCase

from .models import CafeteriaMenu, CafeteriaPaymentCard, CafeteriaWeek


class CafeteriaMenuOrderingTests(TestCase):

    def setUp(self):
        self.week = CafeteriaWeek.objects.create(
            title="هفته آزمایشی",
            start_date=date(2026, 9, 26),
            is_active=True,
        )

    def test_weekday_order_is_saturday_to_wednesday(self):
        creation_order = [
            "monday",
            "wednesday",
            "saturday",
            "tuesday",
            "sunday",
        ]
        for day in creation_order:
            CafeteriaMenu.objects.create(
                week=self.week,
                day=day,
                food_name=f"غذای {day}",
                price=100000,
            )

        ordered_days = list(
            self.week.menus.all()
            .weekday_order()
            .values_list("day", flat=True)
        )

        self.assertEqual(
            ordered_days,
            [
                "saturday",
                "sunday",
                "monday",
                "tuesday",
                "wednesday",
            ],
        )


class CafeteriaPaymentCardTests(TestCase):

    def setUp(self):
        self.week = CafeteriaWeek.objects.create(
            title="هفته کارت‌ها",
            start_date=date(2026, 10, 3),
            is_active=True,
        )

    def test_week_can_have_multiple_payment_cards(self):
        CafeteriaPaymentCard.objects.create(
            week=self.week,
            card_number="1111",
            card_holder="مرضیه شفیعی",
        )
        CafeteriaPaymentCard.objects.create(
            week=self.week,
            card_number="33333",
            card_holder="نیکی ادهمی",
        )

        cards = list(
            self.week.payment_cards.values_list(
                "card_number",
                "card_holder",
            )
        )

        self.assertEqual(
            cards,
            [
                ("1111", "مرضیه شفیعی"),
                ("33333", "نیکی ادهمی"),
            ],
        )
