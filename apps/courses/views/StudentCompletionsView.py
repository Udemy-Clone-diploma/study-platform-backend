from drf_spectacular.utils import extend_schema
from rest_framework import generics

from apps.enrollments.models import CourseCompletion
from apps.enrollments.serializers import CourseCompletionSerializer
from apps.users.permissions import IsStudent


@extend_schema(
    tags=["Courses"],
    summary="List completed courses for the current student",
    description="Returns CourseCompletion records (snapshot data) for the authenticated student, newest first.",
)
class StudentCompletionsView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = CourseCompletionSerializer

    def get_queryset(self):
        qs = (
            CourseCompletion.objects.filter(student_profile=self.request.user.student_profile)
            .select_related("course")
            .prefetch_related("certificates")
        )
        if self.request.query_params.get("with_certificate") == "true":
            # Filtered on the file, not the older certificate_url text column:
            # the file is what the download actually serves, so a row with only
            # a URL would come back as a certificate nothing can open.
            qs = qs.exclude(certificate_file__isnull=True).exclude(certificate_file="")
        return qs
