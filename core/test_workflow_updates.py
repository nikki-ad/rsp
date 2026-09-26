from datetime import date
from io import BytesIO
from zipfile import ZipFile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from academic.models import AcademicYear, Grade, Classroom, Enrollment, TeacherClassAssignment
from accounts.models import TeacherProfile, StudentProfile
from assignments.models import Assignment, AssignmentSubmission
from cafeteria.models import CafeteriaWeek, CafeteriaMenu, CafeteriaReservation
from materials.models import EducationalMaterial
from messaging.models import Conversation, Message


class WorkflowUpdateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.teacher_user = User.objects.create_user(username='teacher', role='teacher')
        cls.teacher = TeacherProfile.objects.create(user=cls.teacher_user)
        cls.student_user = User.objects.create_user(username='student', role='student', first_name='مونا', last_name='احمدی')
        cls.student = StudentProfile.objects.create(user=cls.student_user)
        cls.finance = User.objects.create_user(username='finance', role='finance')
        cls.manager = User.objects.create_user(username='manager', role='school_manager')
        cls.other_user = User.objects.create_user(username='other', role='teacher')
        cls.other = TeacherProfile.objects.create(user=cls.other_user)
        cls.year = AcademicYear.objects.create(title='1405', status='active')
        grade = Grade.objects.create(code='1', title='اول', order=1)
        cls.classroom = Classroom.objects.create(name='یاس', grade=grade, academic_year=cls.year, capacity=30)
        TeacherClassAssignment.objects.create(teacher=cls.teacher, classroom=cls.classroom)
        Enrollment.objects.create(student=cls.student, classroom=cls.classroom, academic_year=cls.year)
        cls.assignment = Assignment.objects.create(title='تکلیف', teacher=cls.teacher, classroom=cls.classroom)
        cls.material = EducationalMaterial.objects.create(title='مطلب', teacher=cls.teacher, content_type='text', content='متن')
        cls.material.classrooms.add(cls.classroom)
        cls.week = CafeteriaWeek.objects.create(title='هفته اول', start_date=date(2026,9,26))
        for day in ('saturday', 'sunday'):
            CafeteriaMenu.objects.create(week=cls.week, day=day, food_name='غذا', price=100)

    def test_edit_assignment_preserves_submissions(self):
        submission = AssignmentSubmission.objects.create(assignment=self.assignment, student=self.student, answer_text='پاسخ')
        self.client.force_login(self.teacher_user)
        r = self.client.post(reverse('edit_assignment', args=[self.assignment.pk]), {'title':'اصلاح', 'description':'جدید'})
        self.assertEqual(r.status_code,302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.title,'اصلاح')
        self.assertTrue(AssignmentSubmission.objects.filter(pk=submission.pk).exists())

    def test_other_teacher_cannot_edit(self):
        self.client.force_login(self.other_user)
        for route, obj in [('edit_assignment',self.assignment),('edit_material',self.material)]:
            self.assertEqual(self.client.post(reverse(route,args=[obj.pk]),{'title':'هک'}).status_code,404)

    def test_student_cannot_edit(self):
        self.client.force_login(self.student_user)
        for route, obj in [('edit_assignment',self.assignment),('edit_material',self.material)]:
            self.assertEqual(self.client.get(reverse(route,args=[obj.pk])).status_code,403)

    def test_material_edit_and_classroom_validation(self):
        self.client.force_login(self.teacher_user)
        url=reverse('edit_material',args=[self.material.pk])
        data={'title':'اصلاح', 'content_type':'text','content':'متن جدید','classrooms':[str(self.classroom.pk)]}
        self.assertEqual(self.client.post(url,data).status_code,302)
        self.material.refresh_from_db()
        self.assertEqual(self.material.content,'متن جدید')
        TeacherClassAssignment.objects.all().delete()
        self.assertEqual(self.client.post(url,data).status_code,403)

    def test_archived_assignment_cannot_be_edited(self):
        self.year.status='archived';self.year.save()
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.get(reverse('edit_assignment',args=[self.assignment.pk])).status_code,404)

    def test_sidebar_and_class_actions(self):
        self.client.force_login(self.teacher_user)
        response=self.client.get(reverse('teacher_class_detail',args=[self.classroom.pk]))
        for route in ['teacher_assignment_list','create_material']:
            self.assertContains(response,reverse(route))
        self.assertContains(response,'افزودن تکلیف')
        self.assertContains(response,'افزودن مطلب')
        self.assertEqual(self.client.get(reverse('teacher_assignment_list')).status_code,200)

    def test_full_week_cannot_be_bypassed_and_retry_is_idempotent(self):
        self.client.force_login(self.student_user)
        url=reverse('weekly_reservation')
        response=self.client.get(url)
        self.assertNotContains(response,'type="checkbox"')
        for _ in range(2):
            self.assertEqual(self.client.post(url,{'menu_fake':False,'final_amount':1}).status_code,302)
        r=CafeteriaReservation.objects.get(student=self.student,week=self.week)
        self.assertEqual(r.final_amount,200)
        self.assertEqual(r.items.filter(wants_food=True).count(),2)

    def test_empty_week_not_reservable(self):
        self.week.menus.all().delete()
        self.client.force_login(self.student_user)
        self.client.post(reverse('weekly_reservation'))
        self.assertEqual(CafeteriaReservation.objects.count(),0)

    def receipt(self,status='receipt_pending'):
        return CafeteriaReservation.objects.create(student=self.student,week=self.week,receipt_image='receipt.png',payment_method='receipt',payment_status=status,final_amount=200)

    def test_review_keeps_receipt_visible_and_exported(self):
        r=self.receipt()
        self.client.force_login(self.finance)
        for action,status in [('approve','paid'),('reject','rejected')]:
            r.payment_status='receipt_pending';r.save()
            response=self.client.post(reverse('cafeteria_review_receipt',args=[r.pk,action]),follow=True)
            self.assertContains(response,'مونا احمدی')
            self.assertContains(response,'receipt-'+status)
            self.assertContains(response,'یاس')
            export=self.client.get(reverse('cafeteria_pending_receipts'),{'export':'xlsx'})
            self.assertEqual(export.status_code,200)
            with ZipFile(BytesIO(export.content)) as z:
                xml=z.read('xl/worksheets/sheet1.xml').decode()
                for text in ['مونا','احمدی','یاس','A1:E2']:
                    self.assertIn(text,xml)

    def test_receipt_filters_and_export_access(self):
        self.receipt('paid')
        self.client.force_login(self.finance)
        response=self.client.get(reverse('cafeteria_pending_receipts'),{'q':'نام ناموجود'})
        self.assertEqual(len(response.context['reservations']),0)
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(reverse('cafeteria_pending_receipts'),{'export':'xlsx'}).status_code,302)

    def test_pending_or_paid_reservation_cannot_change(self):
        r=self.receipt()
        self.client.force_login(self.student_user)
        for status in ['receipt_pending','paid']:
            r.payment_status=status;r.save()
            self.client.post(reverse('weekly_reservation'))
            self.client.post(reverse('cafeteria_upload_receipt',args=[r.pk]))
            r.refresh_from_db()
            self.assertEqual(r.payment_status,status)
            self.assertEqual(r.final_amount,200)

    def test_chat_messages_not_rendered_as_flash_messages(self):
        c=Conversation.objects.create(participant_1=self.teacher_user,participant_2=self.student_user)
        Message.objects.create(conversation=c,sender=self.teacher_user,text='یک پیام واقعی')
        self.client.force_login(self.student_user)
        response=self.client.get(reverse('chat_view',args=[c.pk]))
        self.assertContains(response,'یک پیام واقعی',count=1)
        self.assertNotContains(response,'<ul class="messages">')

    def test_manager_can_edit_announcement_in_place(self):
        from notifications.models import Announcement
        from django.utils import timezone
        announcement = Announcement.objects.create(title='اطلاعیه', message='متن', publish_at=timezone.now())
        self.client.force_login(self.manager)
        response = self.client.post(reverse('announcement_edit', args=[announcement.pk]), {
            'title':'عنوان اصلاح‌شده', 'message':'متن اصلاح‌شده', 'audience':'all',
            'publish_at':'2026-09-26T08:00', 'is_active':'on',
        })
        self.assertEqual(response.status_code,302)
        announcement.refresh_from_db()
        self.assertEqual(announcement.message,'متن اصلاح‌شده')
        self.assertEqual(Announcement.objects.count(),1)
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(reverse('announcement_edit',args=[announcement.pk])).status_code,403)
