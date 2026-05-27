from apps.users.models import StudentProfile, User


def make_student(email="student@example.com"):
    user = User.objects.create_user(
        email=email,
        password="pass12345",
        role=User.RoleChoices.STUDENT,
    )
    profile = StudentProfile.objects.create(user=user)
    return user, profile
