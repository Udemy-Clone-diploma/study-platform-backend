from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import PricingPlan
from apps.courses.serializers import PricingPlanSerializer
from apps.courses.services import PricingPlanService

from ._course_scoped import ensure_can_modify_course, get_course_for_request


@extend_schema(tags=["PricingPlans"])
class PricingPlanListCreateView(generics.ListCreateAPIView):
    """Legacy endpoint: pricing plans nested under a course via delivery_format."""

    serializer_class = PricingPlanSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        course = get_course_for_request(self, self.kwargs["slug"])
        return PricingPlan.objects.filter(delivery_format__course=course)

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use /delivery-formats/ to manage pricing."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


@extend_schema(tags=["PricingPlans"])
class PricingPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Legacy endpoint for reading / patching an individual pricing plan."""

    serializer_class = PricingPlanSerializer
    lookup_url_kwarg = "id"
    http_method_names = ["get", "patch", "delete"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        course = get_course_for_request(self, self.kwargs["slug"])
        return PricingPlan.objects.filter(delivery_format__course=course)

    def partial_update(self, request, *args, **kwargs):
        plan = self.get_object()
        ensure_can_modify_course(request.user, plan.delivery_format.course)
        serializer = self.get_serializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            PricingPlanService.validate_installment_fields(
                serializer.validated_data,
                instance=plan,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        plan = PricingPlanService.update_plan(plan, serializer.validated_data)
        return Response(PricingPlanSerializer(plan).data)

    def destroy(self, request, *args, **kwargs):
        plan = self.get_object()
        ensure_can_modify_course(request.user, plan.delivery_format.course)
        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
