import hashlib
import json
from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
import requests

from . import tests as fixtures
from .models import BBBAttendanceEvent, BBBAttendanceHook
from .attendance import attendance_rows, register_attendance_hook
from .services import build_bbb_meeting_id, get_bbb_live_snapshot


class AttendanceTests(TestCase):
    # Reuse setup without re-running the inherited integration suite.
    def setUp(self):
        fixtures.OnlineClassTests.setUp(self)
        self.now = timezone.now().replace(microsecond=0)
        self.callback = reverse('bbb_attendance_callback', args=[self.config.pk, self.online.pk])
        self.hook = BBBAttendanceHook.objects.create(online_class=self.online, configuration=self.config,
            callback_url='https://rsp.example' + self.callback, registered_at=self.now)
        self.session = 'meeting-internal-1'
        self.client.force_login(self.manager)
        self.url = reverse('live_attendance', args=[self.online.pk])

    def event(self, kind='user-joined', user=None, offset=0, session=None, participant='p1'):
        user = user or self.student_user
        attributes = {'meeting': {'internal-meeting-id': session or self.session,
            'external-meeting-id': build_bbb_meeting_id(self.online)}}
        if kind.startswith('user-'):
            attributes['user'] = {'internal-user-id': participant, 'external-user-id': str(user.pk),
                'name': str(user), 'role': 'MODERATOR' if user == self.teacher_user else 'VIEWER'}
        return {'data': {'id': kind, 'attributes': attributes,
            'event': {'ts': int((self.now + timedelta(seconds=offset)).timestamp()*1000)}}}

    def callback_post(self, events, valid=True, algorithm='sha1', csrf=False):
        body = urlencode({'domain': 'bbb.example', 'event': json.dumps(events, ensure_ascii=False), 'timestamp': '123'})
        checksum = hashlib.new(algorithm, (self.hook.callback_url + body + self.config.secret).encode()).hexdigest()
        if not valid:
            checksum = '0' * len(checksum)
        client = Client(enforce_csrf_checks=True) if csrf else self.client
        return client.post(self.callback + '?checksum=' + checksum, body, content_type='application/x-www-form-urlencoded')

    def live(self, attendees=None, running=True, session=None):
        return {'session_id': (session or self.session) if running else None,
            'attendees': attendees or [], 'running': running}

    def test_signed_callbacks_support_batches_unicode_deduplication_and_no_csrf(self):
        payload = [self.event(offset=-60), self.event('user-left', offset=-10)]
        for algorithm in ('sha1', 'sha256', 'sha384', 'sha512'):
            response = self.callback_post(payload, algorithm=algorithm, csrf=True)
            self.assertEqual(response.status_code, 204)
        self.assertEqual(BBBAttendanceEvent.objects.count(), 2)
        event = BBBAttendanceEvent.objects.first()
        self.assertEqual(event.occurred_at, self.now - timedelta(seconds=60))
        self.hook.refresh_from_db()
        self.assertIsNotNone(self.hook.last_received_at)

    def test_unsigned_forged_and_wrong_class_callbacks_rejected(self):
        self.assertEqual(self.callback_post(self.event(), valid=False).status_code, 403)
        payload = self.event()
        payload['data']['attributes']['meeting']['external-meeting-id'] = 'wrong-class'
        self.assertEqual(self.callback_post(payload).status_code, 400)
        self.assertFalse(BBBAttendanceEvent.objects.exists())

    def test_invalid_batch_is_atomic_and_no_future_or_malformed_times(self):
        for invalid in ({'data': {'id': 'user-joined'}}, self.event(offset=10000)):
            self.assertEqual(self.callback_post([self.event(offset=-20), invalid]).status_code, 400)
            self.assertFalse(BBBAttendanceEvent.objects.exists())

    def test_role_access_enforced_staff_does_not_grant_attendance(self):
        with patch('online_classes.views.get_bbb_live_snapshot', return_value=self.live()):
            self.assertEqual(self.client.get(self.url).status_code, 200)
        for user in (self.student_user, self.teacher_user):
            user.is_staff = True
            user.save()
            self.client.force_login(user)
            with patch('online_classes.views.get_bbb_live_snapshot') as get:
                self.assertEqual(self.client.get(self.url).status_code, 403)
            get.assert_not_called()
            self.assertEqual(self.client.post(reverse('enable_attendance_tracking', args=[self.online.pk])).status_code, 403)

    def test_refresh_snapshot_contains_teachers_students_and_exact_times(self):
        self.callback_post([self.event(offset=-90), self.event('user-left', offset=-50),
            self.event(offset=-20), self.event(user=self.teacher_user, offset=-70, participant='t1')])
        current = self.live([{'user_id': str(self.student_user.pk), 'full_name': 'student', 'role': 'VIEWER'},
            {'user_id': str(self.teacher_user.pk), 'full_name': 'teacher', 'role': 'MODERATOR'}])
        with patch('online_classes.views.get_bbb_live_snapshot', return_value=current) as get:
            response = self.client.get(self.url)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(response.context['student_present'], 1)
        self.assertEqual(response.context['teacher_present'], 1)
        row = next(row for row in response.context['attendance_rows'] if row['kind'] == 'دانش‌آموز')
        self.assertEqual(row['first_join'], self.now - timedelta(seconds=90))
        self.assertEqual(row['last_join'], self.now - timedelta(seconds=20))
        self.assertEqual(row['last_exit'], self.now - timedelta(seconds=50))
        self.assertEqual(len(row['history']), 3)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, 'attendance-snapshot.js')
        self.assertNotContains(response, 'http-equiv="refresh"')

    def test_api_failure_shows_unknown_not_absent_or_zero_counts(self):
        with patch('online_classes.views.get_bbb_live_snapshot', side_effect=requests.Timeout):
            response = self.client.get(self.url)
        self.assertContains(response, 'وضعیت افراد نامشخص است')
        self.assertNotContains(response, 'دانش‌آموزان حاضر:')
        self.assertNotContains(response, 'حضور ثبت نشده')

    def test_new_session_does_not_reuse_old_times_and_no_observation_times_fabricated(self):
        self.callback_post(self.event(offset=-120, session='old-session'))
        current = self.live([{'user_id': str(self.student_user.pk), 'full_name': 'Student'}])
        rows = attendance_rows(self.online, current, timezone.now())
        row = next(row for row in rows if row['user_id'] == str(self.student_user.pk))
        self.assertTrue(row['is_present'])
        self.assertIsNone(row['first_join'])
        self.assertIsNone(row['last_exit'])

    def test_out_of_order_reconnects_are_sorted_by_event_time(self):
        self.callback_post([self.event('user-left', offset=-10), self.event(offset=-60)])
        rows = attendance_rows(self.online, self.live(), timezone.now())
        row = next(row for row in rows if row['user_id'] == str(self.student_user.pk))
        self.assertEqual([event['label'] for event in row['history']], ['ورود', 'خروج'])
        self.assertFalse(row['is_present'])

    def test_ended_meeting_closes_remaining_participants_at_server_end_time(self):
        self.callback_post([self.event(offset=-60), self.event('meeting-ended', offset=-5)])
        rows = attendance_rows(self.online, self.live(running=False), timezone.now())
        row = next(row for row in rows if row['user_id'] == str(self.student_user.pk))
        self.assertEqual(row['last_exit'], self.now - timedelta(seconds=5))
        self.assertFalse(row['is_present'])

    def test_captured_snapshot_does_not_change_until_another_request(self):
        current = self.live([{'user_id': str(self.student_user.pk), 'full_name': 'Student'}])
        with patch('online_classes.views.get_bbb_live_snapshot', return_value=current):
            response = self.client.get(self.url)
        original = response.content
        self.callback_post(self.event('user-left', offset=-5))
        self.assertEqual(response.content, original)
        with patch('online_classes.views.get_bbb_live_snapshot', return_value=self.live()):
            refreshed = self.client.get(self.url)
        self.assertEqual(refreshed.context['student_present'], 0)

    def test_no_match_by_name_or_guest_name_impersonation(self):
        self.student_user.first_name = 'Same Name'
        self.student_user.save()
        rows = attendance_rows(self.online, self.live([{'user_id':'unknown', 'full_name':'Same Name'}]), timezone.now())
        row = next(row for row in rows if row['user_id'] == str(self.student_user.pk))
        self.assertFalse(row['is_present'])
        self.assertEqual(sum(row['is_present'] for row in rows), 1)

    def test_hook_registration_is_signed_scoped_and_throttled(self):
        with patch('online_classes.attendance.requests.get', return_value=Mock(text='<response><returncode>SUCCESS</returncode><hookID>x</hookID></response>')) as get:
            hook = register_attendance_hook(self.online, force=True)
            url = get.call_args.args[0]
            self.assertIn('meetingID=online-class-', url)
            query = url.split('hooks/create?',1)[1]
            params, checksum = query.rsplit('&checksum=',1)
            self.assertEqual(checksum, hashlib.sha1(('hooks/create'+params+self.config.secret).encode()).hexdigest())
            self.assertIsNotNone(hook.registered_at)
            register_attendance_hook(self.online)
            self.assertEqual(get.call_count, 1)

    def test_hook_failure_never_blocks_join(self):
        self.client.force_login(self.student_user)
        with patch('online_classes.views.register_attendance_hook', side_effect=ValueError), patch('online_classes.views.create_bbb_meeting'):
            response = self.client.get(reverse('join_online_class', args=[self.online.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('VIEWER', response.url)

    def test_registration_is_post_only_and_errors_do_not_include_credentials(self):
        url = reverse('enable_attendance_tracking', args=[self.online.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        with patch('online_classes.views.register_attendance_hook', side_effect=ValueError('private-url-secret')):
            with patch('online_classes.views.get_bbb_live_snapshot', return_value=self.live()):
                response = self.client.post(url, follow=True)
        self.assertContains(response, 'Webhooks')
        self.assertNotContains(response, 'private-url-secret')

    def test_snapshot_api_not_found_vs_failure_and_internal_session(self):
        with patch('online_classes.services.requests.get', return_value=Mock(text='<response><returncode>FAILED</returncode><messageKey>notFound</messageKey></response>')):
            self.assertFalse(get_bbb_live_snapshot(self.online)['running'])
        with patch('online_classes.services.requests.get', return_value=Mock(text='<response><returncode>SUCCESS</returncode><internalMeetingID>new</internalMeetingID><attendees><attendee><userID>abc</userID><fullName>A</fullName><role>VIEWER</role></attendee></attendees></response>')):
            self.assertEqual(get_bbb_live_snapshot(self.online)['session_id'], 'new')
        with patch('online_classes.services.requests.get', return_value=Mock(text='<response><returncode>FAILED</returncode><messageKey>checksumError</messageKey></response>')):
            with self.assertRaises(ValueError):
                get_bbb_live_snapshot(self.online)
