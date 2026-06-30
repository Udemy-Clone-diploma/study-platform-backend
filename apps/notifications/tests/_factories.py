from apps.notifications.models import Notification
from apps.users.models import User


def make_user(email, *, role="student", first_name="", last_name=""):
    return User.objects.create_user(
        email=email,
        password="pass12345",
        role=role,
        first_name=first_name,
        last_name=last_name,
    )


def make_notification(recipient, **overrides):
    fields = {
        "type": Notification.TypeChoices.NEW_MESSAGE,
        "title": "Title",
        "body": "Body",
    }
    fields.update(overrides)
    return Notification.objects.create(recipient=recipient, **fields)
