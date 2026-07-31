from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat.models import Message, MessageReport
from apps.chat.services import ChatService
from apps.users.tests._factories import make_user


class ChatUserSerializationTests(APITestCase):
    def setUp(self):
        self.student = make_user(
            role="student",
            email="public-chat-student@example.com",
            first_name="Public",
            last_name="Student",
        )
        self.teacher = make_user(
            role="teacher",
            email="public-chat-teacher@example.com",
        )
        self.chat, _ = ChatService.create_direct_chat(self.student, self.teacher)
        self.message = Message.objects.create(
            chat=self.chat,
            sender=self.student,
            text="Safe chat payload",
        )
        self.chat.last_message = self.message
        self.chat.save(update_fields=["last_message"])

    def test_regular_chat_payloads_do_not_expose_email(self):
        self.client.force_authenticate(self.student)

        chat_response = self.client.get(reverse("chats-list"))
        message_response = self.client.get(
            reverse("chat-messages", args=[self.chat.pk])
        )

        self.assertEqual(chat_response.status_code, status.HTTP_200_OK)
        self.assertEqual(message_response.status_code, status.HTTP_200_OK)

        chat = chat_response.data["results"][0]
        self.assertNotIn("email", chat["created_by"])
        self.assertTrue(
            all("email" not in participant["user"] for participant in chat["participants"])
        )
        self.assertNotIn("email", chat["last_message"]["sender"])
        self.assertNotIn("email", message_response.data["results"][0]["sender"])

    def test_public_chat_name_does_not_fall_back_to_email(self):
        self.client.force_authenticate(self.student)

        response = self.client.get(reverse("chats-list"))

        teacher = next(
            participant["user"]
            for participant in response.data["results"][0]["participants"]
            if participant["user"]["id"] == self.teacher.pk
        )
        self.assertEqual(teacher["name"], "User")
        self.assertNotIn(self.teacher.email, str(response.data))

    def test_moderation_payload_keeps_email(self):
        moderator = make_user(
            role="moderator",
            email="chat-moderator@example.com",
        )
        report = MessageReport.objects.create(
            message=self.message,
            reporter=self.teacher,
            reason=MessageReport.ReasonChoices.SPAM,
            message_text=self.message.text,
        )
        self.client.force_authenticate(moderator)

        response = self.client.get(reverse("moderator-message-reports"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        serialized_report = next(
            item for item in response.data["results"] if item["id"] == report.pk
        )
        self.assertEqual(serialized_report["sender"]["email"], self.student.email)
        self.assertEqual(serialized_report["reporter"]["email"], self.teacher.email)
