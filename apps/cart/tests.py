from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.cart.models import Cart, CartItem
from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_teacher
from apps.enrollments.models import Enrollment
from apps.users.models import StudentProfile, User


def make_student(email="cart_student@example.com"):
    user = User.objects.create_user(
        email=email,
        password="pass12345",
        role=User.RoleChoices.STUDENT,
    )
    profile = StudentProfile.objects.create(user=user)
    return user, profile


class CartApiTests(APITestCase):
    def setUp(self):
        _, self.teacher_profile = make_teacher(email="cart_teacher@example.com")
        self.course = make_course(
            self.teacher_profile,
            title="Cart Course",
            slug="cart-course",
            status=Course.StatusChoices.PUBLISHED,
            price=25,
            pricing_type=Course.PricingTypeChoices.FULL_PAYMENT,
        )
        self.second_course = make_course(
            self.teacher_profile,
            title="Second Cart Course",
            slug="second-cart-course",
            status=Course.StatusChoices.PUBLISHED,
            price=15,
            pricing_type=Course.PricingTypeChoices.FULL_PAYMENT,
        )
        self.draft_course = make_course(
            self.teacher_profile,
            title="Draft Cart Course",
            slug="draft-cart-course",
            status=Course.StatusChoices.DRAFT,
        )
        self.student_user, self.student_profile = make_student()
        self.client.force_authenticate(user=self.student_user)

    def test_get_cart_creates_empty_cart_for_student(self):
        response = self.client.get(reverse("cart-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"], [])
        self.assertEqual(response.data["items_count"], 0)
        self.assertEqual(response.data["total_price"], "0.00")
        self.assertTrue(Cart.objects.filter(student_profile=self.student_profile).exists())

    def test_add_course_to_cart(self):
        response = self.client.post(
            reverse("cart-add-item"),
            {"course_id": self.course.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["items_count"], 1)
        self.assertEqual(response.data["total_price"], "25.00")
        self.assertEqual(response.data["items"][0]["course_id"], self.course.pk)

    def test_cannot_add_draft_course_to_cart(self):
        response = self.client.post(
            reverse("cart-add-item"),
            {"course_id": self.draft_course.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("course_id", response.data)

    def test_cannot_add_duplicate_course_to_cart(self):
        cart = Cart.objects.create(student_profile=self.student_profile)
        CartItem.objects.create(cart=cart, course=self.course)

        response = self.client.post(
            reverse("cart-add-item"),
            {"course_id": self.course.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("course_id", response.data)

    def test_cannot_add_course_with_active_access_to_cart(self):
        Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
        )

        response = self.client.post(
            reverse("cart-add-item"),
            {"course_id": self.course.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("course_id", response.data)

    def test_remove_course_from_cart(self):
        cart = Cart.objects.create(student_profile=self.student_profile)
        CartItem.objects.create(cart=cart, course=self.course)
        CartItem.objects.create(cart=cart, course=self.second_course)

        response = self.client.delete(
            reverse("cart-remove-item", args=[self.course.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items_count"], 1)
        self.assertFalse(cart.items.filter(course=self.course).exists())

    def test_clear_cart(self):
        cart = Cart.objects.create(student_profile=self.student_profile)
        CartItem.objects.create(cart=cart, course=self.course)
        CartItem.objects.create(cart=cart, course=self.second_course)

        response = self.client.delete(reverse("cart-clear"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items_count"], 0)
        self.assertFalse(cart.items.exists())
