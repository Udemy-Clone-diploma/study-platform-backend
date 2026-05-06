from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from apps.courses.models import Category
from apps.courses.serializers import CategorySerializer


class CategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None
