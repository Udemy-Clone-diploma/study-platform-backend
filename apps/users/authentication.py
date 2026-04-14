from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class CustomJWTAuthentication(JWTAuthentication):
    """
    Extends default JWT auth with two extra checks on every authenticated request:
    - Blocked users are rejected.
    - Role in the token must match the user's current role in the DB (SCRUM-123).
      This ensures that role changes invalidate existing access tokens.
    Deleted users are already rejected via ActiveUserManager (User.DoesNotExist -> 401).
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.is_blocked:
            raise AuthenticationFailed("This account has been blocked.")
        token_role = validated_token.get("role")
        if token_role is not None and token_role != user.role:
            raise AuthenticationFailed("Token role does not match current user role.")
        return user
