from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.views._course_scoped import ensure_can_modify_course, get_course_for_request
from apps.curriculum.exceptions import InvalidReorderError, LessonAlreadyHasTestError
from apps.curriculum.models import Lesson, LessonItem, Module
from apps.curriculum.serializers import LessonItemCreateUpdateSerializer, LessonItemSerializer
from apps.curriculum.services import LessonItemService


class _ReorderSerializer(serializers.Serializer):
    item_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


@extend_schema(tags=["Lesson Items"])
class LessonItemViewSet(viewsets.GenericViewSet):
    http_method_names = ["post", "patch", "delete"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def _get_lesson(self, request, kwargs) -> Lesson:
        course = get_course_for_request(self, kwargs["course_slug"])
        ensure_can_modify_course(request.user, course)
        module = get_object_or_404(Module, pk=kwargs["module_pk"], course=course)
        return get_object_or_404(Lesson, pk=kwargs["lesson_pk"], module=module)

    def create(self, request, *args, **kwargs):
        lesson = self._get_lesson(request, kwargs)
        serializer = LessonItemCreateUpdateSerializer(
            data=request.data,
            context={"request": request, "lesson": lesson},
        )
        serializer.is_valid(raise_exception=True)
        try:
            item = LessonItemService.create_item(lesson, serializer.validated_data)
        except LessonAlreadyHasTestError as exc:
            return Response({"item_type": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            LessonItemSerializer(item, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        lesson = self._get_lesson(request, kwargs)
        item = get_object_or_404(LessonItem, pk=kwargs["pk"], lesson=lesson)
        serializer = LessonItemCreateUpdateSerializer(
            item,
            data=request.data,
            partial=True,
            context={"request": request, "lesson": lesson},
        )
        serializer.is_valid(raise_exception=True)
        new_type = serializer.validated_data.get("item_type", item.item_type)
        if new_type == LessonItem.ItemType.TEST:
            try:
                LessonItemService.assert_single_test(lesson, exclude_pk=item.pk)
            except LessonAlreadyHasTestError as exc:
                return Response({"item_type": str(exc)}, status=status.HTTP_409_CONFLICT)
        item = serializer.save()
        return Response(LessonItemSerializer(item, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        lesson = self._get_lesson(request, kwargs)
        item = get_object_or_404(LessonItem, pk=kwargs["pk"], lesson=lesson)
        LessonItemService.soft_delete_item(item)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request, *args, **kwargs):
        lesson = self._get_lesson(request, kwargs)
        serializer = _ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            items = LessonItemService.reorder_items(lesson, serializer.validated_data["item_ids"])
        except InvalidReorderError as exc:
            return Response({"item_ids": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(LessonItemSerializer(items, many=True, context={"request": request}).data)
