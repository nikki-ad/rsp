from django.core.management.base import BaseCommand, CommandError
import requests
from online_classes.models import BBBConfiguration
from online_classes.services import test_bbb_connection


class Command(BaseCommand):
    help = 'Verify active BBB API credentials without creating or changing meetings.'

    def handle(self, *args, **options):
        configs = list(BBBConfiguration.objects.filter(is_active=True))
        if not configs:
            raise CommandError('هیچ سرویس فعال BBB ثبت نشده است.')
        failed = False
        for config in configs:
            try:
                test_bbb_connection(config)
            except (requests.RequestException, ValueError):
                failed = True
                self.stderr.write(f'FAIL: {config.name} — آدرس API، کلید محرمانه یا شبکه را بررسی کنید.')
            else:
                self.stdout.write(self.style.SUCCESS(f'OK: {config.name} — اتصال و کلید API تأیید شد.'))
        if failed:
            raise CommandError('تست اتصال یک یا چند سرویس ناموفق بود.')
