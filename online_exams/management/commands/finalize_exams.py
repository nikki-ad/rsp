from django.core.management.base import BaseCommand
from online_exams.models import Participation
from online_exams.services import ensure_report, finalize_due


class Command(BaseCommand):
    help = "Finalize expired attempts and generate missing private Persian reports. Run every minute."

    def handle(self, *args, **options):
        count = finalize_due()
        failures = 0
        for pk in Participation.objects.filter(submitted_at__isnull=False, result_deleted=False,
                report="", exam__report_files_deleted=False, exam__results_deleted=False
                ).values_list("pk", flat=True).iterator(chunk_size=100):
            try:
                ensure_report(pk)
            except Exception as error:
                failures += 1
                self.stderr.write(f"Report generation failed for {pk}: {type(error).__name__}")
        self.stdout.write(f"Finalized: {count}; report failures: {failures}")
        if failures:
            from django.core.management.base import CommandError
            raise CommandError("Some exam reports could not be generated; retry after fixing dependencies/storage.")
