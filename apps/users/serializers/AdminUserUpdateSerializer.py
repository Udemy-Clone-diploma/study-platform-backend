from .UserUpdateSerializer import UserUpdateSerializer


class AdminUserUpdateSerializer(UserUpdateSerializer):
    """Admin-only user update: self-service fields plus `role`.

    Must never be used on self-service endpoints (/auth/me/), where
    exposing `role` would allow privilege escalation.
    """

    class Meta(UserUpdateSerializer.Meta):
        fields = UserUpdateSerializer.Meta.fields + ["role"]
