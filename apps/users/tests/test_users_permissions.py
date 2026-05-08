from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from apps.users.models import User
from apps.users.permissions import (
    IsAdmin,
    IsAdminOrModerator,
    IsOwnerOrAdmin,
    IsStudent,
    IsTeacher,
)


def _make_user(role, email=None):
    return User.all_objects.create_user(
        email=email or f"{role}@example.com",
        password="pass12345",
        role=role,
        is_email_verified=True,
    )


def _request(user):
    request = RequestFactory().get("/")
    request.user = user
    return request


def _anon_request():
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    return request


class IsAdminTests(TestCase):
    def test_allows_administrator(self):
        perm = IsAdmin()
        user = _make_user("administrator")
        self.assertTrue(perm.has_permission(_request(user), None))
        self.assertTrue(perm.has_object_permission(_request(user), None, object()))

    def test_rejects_other_roles(self):
        perm = IsAdmin()
        for role in ("student", "teacher", "moderator"):
            user = _make_user(role, email=f"admin_test_{role}@example.com")
            self.assertFalse(perm.has_permission(_request(user), None))

    def test_rejects_anonymous(self):
        self.assertFalse(IsAdmin().has_permission(_anon_request(), None))


class IsAdminOrModeratorTests(TestCase):
    def test_allows_admin(self):
        perm = IsAdminOrModerator()
        user = _make_user("administrator", email="aom_admin@example.com")
        self.assertTrue(perm.has_permission(_request(user), None))

    def test_allows_moderator(self):
        perm = IsAdminOrModerator()
        user = _make_user("moderator", email="aom_mod@example.com")
        self.assertTrue(perm.has_permission(_request(user), None))

    def test_rejects_student_and_teacher(self):
        perm = IsAdminOrModerator()
        for role in ("student", "teacher"):
            user = _make_user(role, email=f"aom_{role}@example.com")
            self.assertFalse(perm.has_permission(_request(user), None))


class IsTeacherTests(TestCase):
    def test_allows_teacher(self):
        perm = IsTeacher()
        user = _make_user("teacher", email="teacher_perm@example.com")
        self.assertTrue(perm.has_permission(_request(user), None))

    def test_rejects_other_roles(self):
        perm = IsTeacher()
        for role in ("student", "moderator", "administrator"):
            user = _make_user(role, email=f"teacher_test_{role}@example.com")
            self.assertFalse(perm.has_permission(_request(user), None))


class IsStudentTests(TestCase):
    def test_allows_student(self):
        perm = IsStudent()
        user = _make_user("student", email="student_perm@example.com")
        self.assertTrue(perm.has_permission(_request(user), None))

    def test_rejects_other_roles(self):
        perm = IsStudent()
        for role in ("teacher", "moderator", "administrator"):
            user = _make_user(role, email=f"student_test_{role}@example.com")
            self.assertFalse(perm.has_permission(_request(user), None))


class IsOwnerOrAdminTests(TestCase):
    def test_allows_owner(self):
        perm = IsOwnerOrAdmin()
        user = _make_user("student", email="owner@example.com")
        self.assertTrue(perm.has_object_permission(_request(user), None, user))

    def test_allows_admin_on_any_object(self):
        perm = IsOwnerOrAdmin()
        admin = _make_user("administrator", email="admin_owner@example.com")
        other = _make_user("student", email="other_owner@example.com")
        self.assertTrue(perm.has_object_permission(_request(admin), None, other))

    def test_rejects_non_owner(self):
        perm = IsOwnerOrAdmin()
        user = _make_user("student", email="user_owner@example.com")
        other = _make_user("teacher", email="other2_owner@example.com")
        self.assertFalse(perm.has_object_permission(_request(user), None, other))

    def test_allows_owner_via_user_attr(self):
        class FakeObj:
            pass

        perm = IsOwnerOrAdmin()
        user = _make_user("teacher", email="teacher_obj_owner@example.com")
        obj = FakeObj()
        obj.user = user
        self.assertTrue(perm.has_object_permission(_request(user), None, obj))

    def test_rejects_anonymous(self):
        perm = IsOwnerOrAdmin()
        user = _make_user("student", email="anon_owner_test@example.com")
        self.assertFalse(perm.has_object_permission(_anon_request(), None, user))
