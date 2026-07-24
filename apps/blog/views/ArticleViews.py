from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.blog.exceptions import ArticleAlreadyAssignedError, ArticleNotAssignedToModeratorError, BlogError
from apps.blog.models import Article
from apps.blog.permissions import CanCreateArticle, CanManageArticle
from apps.blog.serializers import ArticleCreateUpdateSerializer, ArticleDetailSerializer, ArticleListSerializer
from apps.blog.services.article_service import ArticleService
from apps.users.models import User
from apps.users.permissions import IsAdminOrModerator

_STAFF_ROLES = (User.RoleChoices.MODERATOR, User.RoleChoices.ADMINISTRATOR)


def _moderator_profile(user):
    return getattr(user, "moderator_profile", None)


@extend_schema(tags=["Blog"])
class ArticleListCreateView(ListCreateAPIView):
    """GET /blog/articles/ — public/own/moderation article listing. POST creates a draft.

    Query params: category=<slug>, mine=true (own articles, any status),
    status=<draft|review|rejected|published|archived> (staff-only unless combined
    with mine=true), assigned=unassigned|mine (staff-only review queue).
    """

    permission_classes = [CanCreateArticle]
    parser_classes = [MultiPartParser, FormParser]
    pagination_class = None

    def get_serializer_class(self):
        return ArticleCreateUpdateSerializer if self.request.method == "POST" else ArticleListSerializer

    def get_queryset(self):
        request = self.request
        user = request.user
        qs = Article.objects.select_related("category", "author", "moderator_profile__user")

        category_slug = request.query_params.get("category")
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(subtitle__icontains=search))

        is_staff = user.is_authenticated and user.role in _STAFF_ROLES

        assigned = request.query_params.get("assigned")
        if assigned and is_staff:
            qs = qs.filter(status=Article.StatusChoices.REVIEW)
            if assigned == "unassigned":
                return qs.filter(moderator_profile__isnull=True).order_by("created_at")
            if assigned == "mine":
                moderator_profile = _moderator_profile(user)
                # An administrator without a ModeratorProfile would otherwise match
                # moderator_profile=None here, which is exactly the "unassigned" queryset.
                if moderator_profile is None:
                    return qs.none()
                return qs.filter(moderator_profile=moderator_profile).order_by("-updated_at")

        if request.query_params.get("mine") == "true":
            if not user.is_authenticated:
                return qs.none()
            qs = qs.filter(author=user)
            status_param = request.query_params.get("status")
            if status_param:
                qs = qs.filter(status=status_param)
            return qs

        status_param = request.query_params.get("status")
        if is_staff and status_param:
            return qs.filter(status=status_param)

        # Published articles are ordered by when they actually went live, not created_at
        # (which reflects the draft's original creation time, not its publish date).
        return qs.filter(status=Article.StatusChoices.PUBLISHED).order_by("-published_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        article = ArticleService.create_article(request.user, serializer.validated_data)
        out = ArticleDetailSerializer(article, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Blog"])
class ArticleDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /blog/articles/{slug}/"""

    lookup_field = "slug"
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [IsAuthenticated(), CanManageArticle()]
        return []

    def get_serializer_class(self):
        return ArticleCreateUpdateSerializer if self.request.method in ("PATCH", "PUT") else ArticleDetailSerializer

    def get_object(self):
        article = get_object_or_404(
            Article.objects.select_related("category", "author", "moderator_profile__user"),
            slug=self.kwargs["slug"],
        )
        user = self.request.user
        is_owner_or_staff = user.is_authenticated and (
            user.role in _STAFF_ROLES or article.author_id == user.id
        )
        is_public = article.status == Article.StatusChoices.PUBLISHED
        if not is_public and not is_owner_or_staff:
            raise NotFound("Article not found.")
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            self.check_object_permissions(self.request, article)
        return article

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        partial = kwargs.pop("partial", True)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        try:
            article = ArticleService.update_article(instance, request.user, serializer.validated_data)
        except BlogError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        out = ArticleDetailSerializer(article, context={"request": request})
        return Response(out.data)

    def destroy(self, request, *args, **kwargs):
        article = self.get_object()
        try:
            ArticleService.delete_article(article, request.user)
        except BlogError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class _ArticleActionView(APIView):
    """Base for the simple author-or-staff state-transition endpoints."""

    permission_classes = [IsAuthenticated, CanManageArticle]
    service_method_name = ""

    def post(self, request, slug):
        article = get_object_or_404(Article.objects, slug=slug)
        self.check_object_permissions(request, article)
        service_method = getattr(ArticleService, self.service_method_name)
        try:
            article = service_method(article, request.user)
        except BlogError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(ArticleDetailSerializer(article, context={"request": request}).data)


@extend_schema(tags=["Blog"])
class ArticleSubmitReviewView(_ArticleActionView):
    """POST /blog/articles/{slug}/submit/ — teacher submits a draft/rejected article for moderation."""

    service_method_name = "submit_for_review"


@extend_schema(tags=["Blog"])
class ArticlePublishView(_ArticleActionView):
    """POST /blog/articles/{slug}/publish/ — moderator/admin publishes their own draft directly."""

    service_method_name = "publish_own_article"


@extend_schema(tags=["Blog"])
class ArticleWithdrawView(_ArticleActionView):
    """POST /blog/articles/{slug}/withdraw/ — author pulls a review/published article back to draft."""

    service_method_name = "withdraw_to_draft"


@extend_schema(tags=["Blog"])
class ArticleArchiveView(_ArticleActionView):
    """POST /blog/articles/{slug}/archive/ — shelve a published article (or, for staff, any article)."""

    service_method_name = "archive_article"


@extend_schema(tags=["Blog"])
class ArticleRestoreView(_ArticleActionView):
    """POST /blog/articles/{slug}/restore/ — bring an archived article back to draft."""

    service_method_name = "restore_from_archive"


@extend_schema(tags=["Blog"])
class ArticleAssignModeratorView(APIView):
    """POST /blog/articles/{slug}/assign-moderator/ — claim an under-review article from the shared queue."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        article = get_object_or_404(Article.objects, slug=slug)
        try:
            ArticleService.assign_moderator_self(article, _moderator_profile(request.user))
        except ArticleAlreadyAssignedError:
            return Response({"detail": "This article already has a moderator assigned."}, status=status.HTTP_409_CONFLICT)
        except BlogError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"detail": "Moderator assigned."})


@extend_schema(tags=["Blog"])
class ArticleApproveView(APIView):
    """POST /blog/articles/{slug}/approve/ — publish an article the requester is assigned to review."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        article = get_object_or_404(Article.objects, slug=slug)
        try:
            article = ArticleService.approve_article(article, _moderator_profile(request.user))
        except ArticleNotAssignedToModeratorError:
            return Response({"detail": "Assign yourself to this article before moderating it."}, status=status.HTTP_409_CONFLICT)
        except BlogError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(ArticleDetailSerializer(article, context={"request": request}).data)


@extend_schema(tags=["Blog"])
class ArticleRejectView(APIView):
    """POST /blog/articles/{slug}/reject/ — return an article under review with a comment."""

    permission_classes = [IsAdminOrModerator]

    def post(self, request, slug):
        article = get_object_or_404(Article.objects, slug=slug)
        try:
            article = ArticleService.reject_article(article, _moderator_profile(request.user), request.data.get("comment", ""))
        except ArticleNotAssignedToModeratorError:
            return Response({"detail": "Assign yourself to this article before moderating it."}, status=status.HTTP_409_CONFLICT)
        except BlogError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(ArticleDetailSerializer(article, context={"request": request}).data)
