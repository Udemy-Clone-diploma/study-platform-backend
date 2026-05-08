from apps.users.models import User


def make_user(role="student", email=None, *, verified=True, **overrides):
    user = User.all_objects.create_user(
        email=email or f"{role}@example.com",
        password="pass12345",
        role=role,
        is_email_verified=verified,
        **overrides,
    )
    return user


def authenticate_as_admin(client, email="admin_setup@example.com"):
    admin = make_user(role=User.RoleChoices.ADMINISTRATOR, email=email)
    client.force_authenticate(user=admin)
    return admin
