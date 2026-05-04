from rest_framework import serializers

from apps.courses.models import Category, Course, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description"]


class CourseListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title", "short_description", "slug", "teacher_name", "category",
            "level", "language", "mode", "delivery_type", "course_type", "pricing_type",
            "price", "duration_hours", "lessons_count", "with_certificate", "is_on_sale",
            "rating_avg", "students_count", "status", "published_at", "tags",
        ]

    def get_teacher_name(self, obj):
        user = obj.teacher_profile.user
        return f"{user.first_name} {user.last_name}".strip()


class CourseDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    teacher_name = serializers.SerializerMethodField()
    teacher_id = serializers.IntegerField(source="teacher_profile.id", read_only=True)
    moderator_id = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title", "short_description", "full_description", "slug", "teacher_id",
            "teacher_name", "moderator_id", "category", "level", "language", "mode",
            "delivery_type", "course_type", "pricing_type", "price", "installment_count",
            "installment_amount", "duration_hours", "lessons_count",
            "with_certificate", "is_on_sale", "rating_avg", "students_count", "status", "created_at",
            "updated_at", "published_at", "tags",
        ]

    def get_teacher_name(self, obj):
        user = obj.teacher_profile.user
        return f"{user.first_name} {user.last_name}".strip()

    def get_moderator_id(self, obj):
        return obj.moderator_profile.id if obj.moderator_profile else None


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        required=False,
        allow_null=True,
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        source="tags",
        required=False,
    )

    class Meta:
        model = Course
        fields = [
            "title", "short_description", "full_description", "teacher_profile",
            "moderator_profile", "category_id", "level", "language", "mode", "delivery_type",
            "course_type", "pricing_type", "price", "installment_count", "installment_amount",
            "duration_hours", "lessons_count", "with_certificate",
            "is_on_sale", "status", "tag_ids",
        ]

    def validate(self, attrs):
        mode = attrs.get("mode", getattr(self.instance, "mode", None))
        delivery_type = attrs.get(
            "delivery_type",
            getattr(self.instance, "delivery_type", None),
        )

        if mode == Course.ModeChoices.SELF_LEARNING and delivery_type not in {
            Course.DeliveryTypeChoices.SELF_PACED,
            Course.DeliveryTypeChoices.SCHEDULED,
        }:
            raise serializers.ValidationError(
                {
                    "delivery_type": (
                        "For self_learning courses, delivery_type must be "
                        "self_paced or scheduled."
                    )
                }
            )

        if mode == Course.ModeChoices.WITH_TEACHER and delivery_type not in {
            Course.DeliveryTypeChoices.INDIVIDUAL,
            Course.DeliveryTypeChoices.GROUP,
        }:
            raise serializers.ValidationError(
                {
                    "delivery_type": (
                        "For with_teacher courses, delivery_type must be "
                        "individual or group."
                    )
                }
            )

        pricing_type = attrs.get("pricing_type", getattr(self.instance, "pricing_type", None))
        errors = {}
        if pricing_type == Course.PricingTypeChoices.INSTALLMENT:
            if not attrs.get("installment_count") and not getattr(self.instance, "installment_count", None):
                errors["installment_count"] = "installment_count is required for installment pricing."
            if not attrs.get("installment_amount") and not getattr(self.instance, "installment_amount", None):
                errors["installment_amount"] = "installment_amount is required for installment pricing."
        if errors:
            raise serializers.ValidationError(errors)

        return attrs
