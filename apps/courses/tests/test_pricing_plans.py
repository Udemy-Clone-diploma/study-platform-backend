from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course, PricingPlan
from apps.users.models import User

from ._factories import make_course, make_pricing_plan, make_teacher


class PricingPlanReadTests(APITestCase):
    def setUp(self):
        _, self.teacher_profile = make_teacher(email="pp_teacher@example.com")
        self.published = make_course(
            self.teacher_profile,
            slug="published",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.draft = make_course(
            self.teacher_profile,
            title="Draft",
            slug="draft",
            status=Course.StatusChoices.DRAFT,
        )
        make_pricing_plan(self.published, format_type="group", price="100.00")
        make_pricing_plan(self.published, format_type="individual", price="200.00")

    def test_anonymous_can_list_plans_for_published_course(self):
        response = self.client.get(reverse("pricing-plans-list", args=[self.published.slug]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_anonymous_cannot_see_plans_on_draft_course(self):
        make_pricing_plan(self.draft)
        response = self.client.get(reverse("pricing-plans-list", args=[self.draft.slug]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_see_plans_on_their_draft_course(self):
        make_pricing_plan(self.draft)
        self.client.force_authenticate(user=self.teacher_profile.user)
        response = self.client.get(reverse("pricing-plans-list", args=[self.draft.slug]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)


class PricingPlanWriteTests(APITestCase):
    def setUp(self):
        _, self.owner_profile = make_teacher(email="owner_pp@example.com")
        _, self.other_profile = make_teacher(email="other_pp@example.com")
        self.admin = User.objects.create_user(
            email="admin_pp@example.com",
            password="pass12345",
            role=User.RoleChoices.ADMINISTRATOR,
        )
        self.course = make_course(
            self.owner_profile,
            slug="some-course",
            status=Course.StatusChoices.PUBLISHED,
        )

    def _payload(self, **overrides):
        data = {
            "price": "150.00",
            "currency": PricingPlan.CurrencyChoices.USD,
        }
        data.update(overrides)
        return data

    def test_anonymous_cannot_create(self):
        response = self.client.post(
            reverse("pricing-plans-list", args=[self.course.slug]),
            self._payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_post_returns_405(self):
        self.client.force_authenticate(user=self.owner_profile.user)
        response = self.client.post(
            reverse("pricing-plans-list", args=[self.course.slug]),
            self._payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_owner_can_patch(self):
        plan = make_pricing_plan(self.course, price="100.00")
        self.client.force_authenticate(user=self.owner_profile.user)
        response = self.client.patch(
            reverse("pricing-plans-detail", args=[self.course.slug, plan.pk]),
            {"price": "175.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plan.refresh_from_db()
        self.assertEqual(str(plan.price), "175.00")

    def test_owner_can_delete(self):
        plan = make_pricing_plan(self.course)
        self.client.force_authenticate(user=self.owner_profile.user)
        response = self.client.delete(
            reverse("pricing-plans-detail", args=[self.course.slug, plan.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PricingPlan.objects.filter(pk=plan.pk).exists())


class PricingPlanInstallmentValidationTests(APITestCase):
    def setUp(self):
        _, self.owner_profile = make_teacher(email="inst_pp@example.com")
        self.course = make_course(
            self.owner_profile,
            slug="course-inst",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.client.force_authenticate(user=self.owner_profile.user)

    def test_post_returns_405(self):
        response = self.client.post(
            reverse("pricing-plans-list", args=[self.course.slug]),
            {"price": "100.00", "installment_count": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_installment_validation_count_only_rejected(self):
        plan = make_pricing_plan(self.course, price="100.00")
        response = self.client.patch(
            reverse("pricing-plans-detail", args=[self.course.slug, plan.pk]),
            {"installment_count": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_installment_count_below_two_rejected(self):
        plan = make_pricing_plan(self.course, price="100.00")
        response = self.client.patch(
            reverse("pricing-plans-detail", args=[self.course.slug, plan.pk]),
            {"installment_count": 1, "installment_amount": "100.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_installments_must_cover_price(self):
        plan = make_pricing_plan(self.course, price="100.00")
        response = self.client.patch(
            reverse("pricing-plans-detail", args=[self.course.slug, plan.pk]),
            {"installment_count": 3, "installment_amount": "20.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_valid_installment_plan_accepted(self):
        plan = make_pricing_plan(self.course, format_type="individual", price="100.00")
        response = self.client.patch(
            reverse("pricing-plans-detail", args=[self.course.slug, plan.pk]),
            {"installment_count": 4, "installment_amount": "25.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
