from django.test import TestCase
from organizations.models import Organization


class SoftDeleteTests(TestCase):
    def test_soft_delete_marks_and_filters(self):
        org = Organization.objects.create(name="Acme")
        self.assertEqual(Organization.objects.count(), 1)
        org.delete()
        org.refresh_from_db()
        self.assertTrue(org.is_deleted)
        self.assertIsNotNone(org.deleted_at)
        self.assertEqual(Organization.objects.count(), 0)
        self.assertEqual(Organization.all_objects.count(), 1)

    def test_restore(self):
        org = Organization.objects.create(name="RestoreCo")
        org.delete()
        org.restore()
        self.assertFalse(org.is_deleted)
        self.assertIsNone(org.deleted_at)
        self.assertEqual(Organization.objects.count(), 1)

    def test_queryset_delete_and_hard_delete(self):
        org = Organization.objects.create(name="HardCo")
        Organization.objects.filter(pk=org.pk).delete()
        self.assertEqual(Organization.objects.count(), 0)
        self.assertEqual(Organization.all_objects.count(), 1)
        Organization.all_objects.filter(pk=org.pk).delete(hard=True)
        self.assertEqual(Organization.all_objects.count(), 0)
