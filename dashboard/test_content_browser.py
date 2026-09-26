from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from core.test_workflow_updates import WorkflowUpdateTests
from academic.models import Classroom
from assignments.models import Assignment
from materials.models import EducationalMaterial


class ManagerContentBrowserTests(TestCase):
    setUpTestData = classmethod(WorkflowUpdateTests.setUpTestData.__func__)

    def setUp(self):
        self.teacher_user.first_name = 'سارا'
        self.teacher_user.last_name = 'معلم'
        self.teacher_user.save()
        self.other_user.first_name = 'مریم'
        self.other_user.last_name = 'دبیر'
        self.other_user.save()
        self.new_material = EducationalMaterial.objects.create(title='مطلب جدید دوم', content_type='text', content='متن', teacher=self.other)
        self.new_material.classrooms.add(self.classroom)
        self.new_assignment = Assignment.objects.create(title='تکلیف جدید دوم', teacher=self.other, classroom=self.classroom)
        old_time = timezone.now() - timedelta(days=1)
        EducationalMaterial.objects.filter(pk=self.material.pk).update(created_at=old_time)
        Assignment.objects.filter(pk=self.assignment.pk).update(created_at=old_time)
        self.extra_class = Classroom.objects.create(academic_year=self.year, grade=self.classroom.grade, name='کلاس دیگر', capacity=20)
        other = EducationalMaterial.objects.create(title='مطلب کلاس دیگر', teacher=self.teacher)
        other.classrooms.add(self.extra_class)
        Assignment.objects.create(title='تکلیف کلاس دیگر', teacher=self.teacher, classroom=self.extra_class)

    def test_both_manager_roles_can_browse_all_authors_in_order(self):
        admin = get_user_model().objects.create_user(username='system.admin', role='super_admin')
        for user in [self.manager, admin]:
            self.client.force_login(user)
            for kind in ['material', 'assignment']:
                response = self.client.get(reverse('manager_'+kind+'_classrooms'))
                self.assertContains(response,self.classroom.name)
                self.assertContains(response,self.extra_class.name)
                for route in ['manager_material_classrooms','manager_assignment_classrooms']:
                    self.assertContains(response,reverse(route))
            for kind,new,old in [('materials',self.new_material,self.material),('assignments',self.new_assignment,self.assignment)]:
                response = self.client.get(reverse('manager_class_'+kind,args=[self.classroom.pk]))
                self.assertEqual(response.status_code,200)
                self.assertEqual(list(response.context['page_obj']),[new,old])
                for name in ['سارا معلم','مریم دبیر']:
                    self.assertContains(response,name)
                self.assertNotContains(response,'مطلب کلاس دیگر')
                self.assertNotContains(response,'تکلیف کلاس دیگر')

    def test_non_managers_cannot_access_lists_or_class_content(self):
        for user in [self.teacher_user,self.student_user,self.finance]:
            self.client.force_login(user)
            for name,args in [('manager_material_classrooms',[]),('manager_assignment_classrooms',[]),('manager_class_materials',[self.classroom.pk]),('manager_class_assignments',[self.classroom.pk])]:
                self.assertEqual(self.client.get(reverse(name,args=args)).status_code,403)

    def test_archive_is_readable_and_empty_class_has_message(self):
        self.client.force_login(self.manager)
        self.year.status='archived';self.year.save()
        self.assertContains(self.client.get(reverse('manager_class_materials',args=[self.classroom.pk])),self.material.title)
        self.extra_class.materials.clear()
        self.assertContains(self.client.get(reverse('manager_class_materials',args=[self.extra_class.pk])),'هنوز محتوایی')

    def test_pagination_keeps_every_item_accessible(self):
        for i in range(31):
            Assignment.objects.create(title=f'تکلیف {i}',teacher=self.teacher,classroom=self.classroom)
        self.client.force_login(self.manager)
        url=reverse('manager_class_assignments',args=[self.classroom.pk])
        first=self.client.get(url).context['page_obj']
        second=self.client.get(url,{'page':2}).context['page_obj']
        self.assertEqual(len(first),30)
        self.assertEqual(len(second),3)
        self.assertEqual(len({x.pk for x in [*first,*second]}),33)
