from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Notification


class NotificationSummaryTests(TestCase):
    def test_existing_content_notifications_show_only_summaries_and_are_acknowledged(self):
        user = get_user_model().objects.create_user(username='summary-student', role='student')
        other = get_user_model().objects.create_user(username='other-student', role='student')
        self.client.force_login(user)
        for kind, destination in [('material', 'مطالب آموزشی'), ('assignment', 'تکالیف'), ('announcement', 'اطلاعیه‌ها')]:
            with self.subTest(kind=kind):
                Notification.objects.all().delete()
                item = Notification.objects.create(recipient=user, notification_type=kind,
                    title='عنوان اعلان', message='متن کامل محرمانه', url='/old-content/')
                outsider = Notification.objects.create(recipient=other, notification_type=kind, title='اعلان شخص دیگر')
                response = self.client.get(reverse('notification_list'))
                self.assertContains(response, f'به بخش «{destination}» مراجعه کنید.')
                self.assertNotContains(response, 'متن کامل محرمانه')
                self.assertNotContains(response, reverse('open_notification', args=[item.pk]))
                self.assertNotContains(response, 'اعلان شخص دیگر')
                item.refresh_from_db()
                outsider.refresh_from_db()
                self.assertTrue(item.is_read)
                self.assertFalse(outsider.is_read)
                self.assertEqual(item.message, 'متن کامل محرمانه')

    def test_message_notifications_keep_their_open_flow(self):
        user = get_user_model().objects.create_user(username='message-student', role='student')
        self.client.force_login(user)
        item = Notification.objects.create(recipient=user, notification_type='message',
            title='پیام', message='متن پیام', url='/messages/')
        response = self.client.get(reverse('notification_list'))
        self.assertContains(response, 'متن پیام')
        self.assertContains(response, reverse('open_notification', args=[item.pk]))
        item.refresh_from_db()
        self.assertFalse(item.is_read)
