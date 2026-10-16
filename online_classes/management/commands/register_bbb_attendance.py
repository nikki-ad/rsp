from django.core.management.base import BaseCommand
import requests
from online_classes.attendance import register_attendance_hook
from online_classes.models import OnlineClass


class Command(BaseCommand):
    help = 'Register signed BBB attendance callbacks for active online classes.'

    def handle(self, *args, **options):
        classes = OnlineClass.objects.filter(is_active=True, provider='bbb',
            academic_year__status='active', bbb_configuration__is_active=True).select_related('bbb_configuration')
        if not classes.exists():
            self.stdout.write('No active BBB classes. Tracking will be requested when a class is entered.')
        for online_class in classes:
            try:
                register_attendance_hook(online_class, force=True)
            except (requests.RequestException, ValueError):
                self.stderr.write(f'NOT VERIFIED: {online_class.title} — provider Webhooks/network must be checked.')
            else:
                self.stdout.write(f'REGISTERED: {online_class.title} — confirm by joining, leaving, then refreshing attendance.')
