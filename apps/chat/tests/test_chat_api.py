from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.chat.consumers import ONLINE_USER_CONNECTIONS
from apps.chat.models import ChatParticipant, ChatRoom, ChatUserBlock, Message
from apps.chat.services import ChatService
from apps.users.tests._factories import make_user
from config.asgi import application


class ChatApiTests(APITestCase):
    def setUp(self):
        self.student = make_user(role="student", email="chat_student@example.com")
        self.teacher = make_user(role="teacher", email="chat_teacher@example.com")
        self.other = make_user(role="student", email="chat_other@example.com")

    def test_create_direct_chat_and_prevent_duplicate(self):
        self.client.force_authenticate(self.student)
        url = reverse("chats-direct")

        first = self.client.post(url, {"user_id": self.teacher.id}, format="json")
        second = self.client.post(url, {"user_id": self.teacher.id}, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(ChatRoom.objects.filter(type=ChatRoom.TypeChoices.DIRECT).count(), 1)
        self.assertEqual(ChatParticipant.objects.filter(chat_id=first.data["id"]).count(), 2)

    def test_create_group_chat_and_list_only_user_chats(self):
        self.client.force_authenticate(self.student)

        response = self.client.post(
            reverse("chats-group"),
            {"title": "Course cohort", "participant_ids": [self.teacher.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        chat_id = response.data["id"]
        self.assertEqual(response.data["type"], ChatRoom.TypeChoices.GROUP)

        owner_list = self.client.get(reverse("chats-list"))
        self.assertEqual(owner_list.status_code, status.HTTP_200_OK)
        self.assertEqual([chat["id"] for chat in owner_list.data["results"]], [chat_id])

        self.client.force_authenticate(self.other)
        other_list = self.client.get(reverse("chats-list"))
        self.assertEqual(other_list.status_code, status.HTTP_200_OK)
        self.assertEqual(other_list.data["results"], [])

    def test_messages_are_visible_only_to_active_participants(self):
        chat, _ = ChatService.create_direct_chat(self.student, self.teacher)
        Message.objects.create(chat=chat, sender=self.student, text="Private note")

        self.client.force_authenticate(self.teacher)
        participant_response = self.client.get(reverse("chat-messages", args=[chat.id]))
        self.assertEqual(participant_response.status_code, status.HTTP_200_OK)
        self.assertEqual(participant_response.data["results"][0]["text"], "Private note")

        self.client.force_authenticate(self.other)
        outsider_response = self.client.get(reverse("chat-messages", args=[chat.id]))
        self.assertEqual(outsider_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_rest_send_message_and_mark_read(self):
        chat, _ = ChatService.create_direct_chat(self.student, self.teacher)
        self.client.force_authenticate(self.student)

        send_response = self.client.post(
            reverse("chat-messages", args=[chat.id]),
            {"text": "Hello from REST"},
            format="json",
        )

        self.assertEqual(send_response.status_code, status.HTTP_201_CREATED)
        message = Message.objects.get(pk=send_response.data["id"])
        chat.refresh_from_db()
        self.assertEqual(chat.last_message, message)

        self.client.force_authenticate(self.teacher)
        read_response = self.client.post(
            reverse("chat-read", args=[chat.id]),
            {"message_id": message.id},
            format="json",
        )
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(read_response.data["last_read_message"], message.id)

    def test_participant_management_requires_owner_or_admin(self):
        chat = ChatService.create_group_chat(self.student, "Study group", [self.teacher.id])

        self.client.force_authenticate(self.teacher)
        denied_response = self.client.post(
            reverse("chat-participants", args=[chat.id]),
            {"user_ids": [self.other.id]},
            format="json",
        )
        self.assertEqual(denied_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.student)
        allowed_response = self.client.post(
            reverse("chat-participants", args=[chat.id]),
            {"user_ids": [self.other.id]},
            format="json",
        )
        self.assertEqual(allowed_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ChatParticipant.objects.filter(chat=chat, user=self.other, left_at__isnull=True).exists()
        )

    def test_only_sender_can_edit_and_delete_message(self):
        chat, _ = ChatService.create_direct_chat(self.student, self.teacher)
        message = Message.objects.create(chat=chat, sender=self.student, text="Original")

        self.client.force_authenticate(self.teacher)
        denied_edit = self.client.patch(
            reverse("chat-message-detail", args=[message.id]),
            {"text": "Edited by recipient"},
            format="json",
        )
        self.assertEqual(denied_edit.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.student)
        edit_response = self.client.patch(
            reverse("chat-message-detail", args=[message.id]),
            {"text": "Edited"},
            format="json",
        )
        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(edit_response.data["text"], "Edited")

        delete_response = self.client.delete(reverse("chat-message-detail", args=[message.id]))
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        message.refresh_from_db()
        self.assertTrue(message.is_deleted)

    def test_mute_and_block_direct_chat(self):
        chat, _ = ChatService.create_direct_chat(self.student, self.teacher)
        self.client.force_authenticate(self.student)

        mute_response = self.client.patch(
            reverse("chats-mute", args=[chat.id]),
            {"is_muted": True},
            format="json",
        )
        self.assertEqual(mute_response.status_code, status.HTTP_200_OK)
        self.assertTrue(mute_response.data["is_muted"])
        self.assertTrue(
            ChatParticipant.objects.get(chat=chat, user=self.student).is_muted
        )

        block_response = self.client.patch(
            reverse("chats-block", args=[chat.id]),
            {"is_blocked": True},
            format="json",
        )
        self.assertEqual(block_response.status_code, status.HTTP_200_OK)
        self.assertTrue(block_response.data["is_blocked"])
        self.assertTrue(
            ChatUserBlock.objects.filter(blocker=self.student, blocked=self.teacher).exists()
        )

        blocked_send = self.client.post(
            reverse("chat-messages", args=[chat.id]),
            {"text": "Blocked send"},
            format="json",
        )
        self.assertEqual(blocked_send.status_code, status.HTTP_403_FORBIDDEN)

        unblock_response = self.client.patch(
            reverse("chats-block", args=[chat.id]),
            {"is_blocked": False},
            format="json",
        )
        self.assertEqual(unblock_response.status_code, status.HTTP_200_OK)
        self.assertFalse(unblock_response.data["is_blocked"])
        self.assertFalse(
            ChatUserBlock.objects.filter(blocker=self.student, blocked=self.teacher).exists()
        )

        allowed_send = self.client.post(
            reverse("chat-messages", args=[chat.id]),
            {"text": "Allowed send"},
            format="json",
        )
        self.assertEqual(allowed_send.status_code, status.HTTP_201_CREATED)

    def test_clear_history_only_hides_messages_for_current_user(self):
        chat, _ = ChatService.create_direct_chat(self.student, self.teacher)
        Message.objects.create(chat=chat, sender=self.student, text="First")
        Message.objects.create(chat=chat, sender=self.teacher, text="Second")

        self.client.force_authenticate(self.student)
        clear_response = self.client.post(reverse("chats-clear-history", args=[chat.id]))
        self.assertEqual(clear_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(clear_response.data["last_message"])

        student_messages = self.client.get(reverse("chat-messages", args=[chat.id]))
        self.assertEqual(student_messages.status_code, status.HTTP_200_OK)
        self.assertEqual(student_messages.data["results"], [])

        self.client.force_authenticate(self.teacher)
        teacher_messages = self.client.get(reverse("chat-messages", args=[chat.id]))
        self.assertEqual(teacher_messages.status_code, status.HTTP_200_OK)
        self.assertEqual(len(teacher_messages.data["results"]), 2)

        new_message = Message.objects.create(chat=chat, sender=self.teacher, text="After clear")
        ChatRoom.objects.filter(pk=chat.pk).update(last_message=new_message)

        self.client.force_authenticate(self.student)
        updated_messages = self.client.get(reverse("chat-messages", args=[chat.id]))
        self.assertEqual(updated_messages.status_code, status.HTTP_200_OK)
        self.assertEqual(len(updated_messages.data["results"]), 1)
        self.assertEqual(updated_messages.data["results"][0]["text"], "After clear")

    def test_delete_chat_removes_it_for_all_participants(self):
        chat, _ = ChatService.create_direct_chat(self.student, self.teacher)
        self.client.force_authenticate(self.student)

        delete_response = self.client.delete(reverse("chats-detail", args=[chat.id]))
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        chat.refresh_from_db()
        self.assertTrue(chat.is_deleted)
        self.assertFalse(
            ChatParticipant.objects.filter(chat=chat, left_at__isnull=True).exists()
        )

        self.client.force_authenticate(self.teacher)
        teacher_list = self.client.get(reverse("chats-list"))
        self.assertEqual(teacher_list.status_code, status.HTTP_200_OK)
        self.assertEqual(teacher_list.data["results"], [])


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class ChatWebSocketTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        ONLINE_USER_CONNECTIONS.clear()
        self.student = make_user(role="student", email="ws_student@example.com")
        self.teacher = make_user(role="teacher", email="ws_teacher@example.com")
        self.other = make_user(role="student", email="ws_other@example.com")
        self.chat, _ = ChatService.create_direct_chat(self.student, self.teacher)

    def _headers_for(self, user):
        token = str(AccessToken.for_user(user))
        return [
            (b"host", b"testserver"),
            (b"origin", b"http://testserver"),
            (b"cookie", f"access_token={token}".encode()),
        ]

    async def _receive_type(self, communicator, event_type: str, attempts: int = 6):
        for _ in range(attempts):
            event = await communicator.receive_json_from(timeout=2)
            if event.get("type") == event_type:
                return event
        raise AssertionError(f"Did not receive {event_type}")

    def test_websocket_rejects_unauthenticated_user(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                application,
                "/ws/chat/",
                headers=[(b"host", b"testserver"), (b"origin", b"http://testserver")],
            )
            connected, _ = await communicator.connect()
            self.assertFalse(connected)

        async_to_sync(scenario)()

    def test_websocket_message_send_broadcasts_to_participants_only(self):
        sender_headers = self._headers_for(self.student)
        recipient_headers = self._headers_for(self.teacher)
        outsider_headers = self._headers_for(self.other)

        async def scenario():
            sender = WebsocketCommunicator(
                application,
                "/ws/chat/",
                headers=sender_headers,
            )
            recipient = WebsocketCommunicator(
                application,
                "/ws/chat/",
                headers=recipient_headers,
            )
            outsider = WebsocketCommunicator(
                application,
                "/ws/chat/",
                headers=outsider_headers,
            )
            self.assertTrue((await sender.connect())[0])
            self.assertTrue((await recipient.connect())[0])
            self.assertTrue((await outsider.connect())[0])
            outsider_snapshot = await self._receive_type(outsider, "presence.snapshot")
            self.assertEqual(outsider_snapshot["online_user_ids"], [])

            await sender.send_json_to(
                {
                    "type": "message.send",
                    "payload": {"chat_id": self.chat.id, "text": "Live message"},
                }
            )

            sender_event = await self._receive_type(sender, "message.created")
            recipient_event = await self._receive_type(recipient, "message.created")
            self.assertEqual(sender_event["message"]["text"], "Live message")
            self.assertEqual(recipient_event["message"]["text"], "Live message")
            self.assertTrue(await outsider.receive_nothing(timeout=0.2))

            await sender.disconnect()
            await recipient.disconnect()
            await outsider.disconnect()

        async_to_sync(scenario)()

    def test_websocket_presence_reports_connected_peers(self):
        student_headers = self._headers_for(self.student)
        teacher_headers = self._headers_for(self.teacher)

        async def scenario():
            student = WebsocketCommunicator(
                application,
                "/ws/chat/",
                headers=student_headers,
            )
            teacher = WebsocketCommunicator(
                application,
                "/ws/chat/",
                headers=teacher_headers,
            )

            self.assertTrue((await student.connect())[0])
            student_snapshot = await self._receive_type(student, "presence.snapshot")
            self.assertEqual(student_snapshot["online_user_ids"], [])

            self.assertTrue((await teacher.connect())[0])
            teacher_snapshot = await self._receive_type(teacher, "presence.snapshot")
            self.assertIn(self.student.id, teacher_snapshot["online_user_ids"])

            online_event = await self._receive_type(student, "presence")
            self.assertEqual(online_event["user_id"], self.teacher.id)
            self.assertTrue(online_event["is_online"])

            await teacher.disconnect()
            offline_event = await self._receive_type(student, "presence")
            self.assertEqual(offline_event["user_id"], self.teacher.id)
            self.assertFalse(offline_event["is_online"])

            await student.disconnect()

        async_to_sync(scenario)()

    def test_websocket_rejects_unauthorized_chat_id(self):
        private_chat, _ = ChatService.create_direct_chat(self.teacher, self.other)
        headers = self._headers_for(self.student)

        async def scenario():
            communicator = WebsocketCommunicator(
                application,
                "/ws/chat/",
                headers=headers,
            )
            self.assertTrue((await communicator.connect())[0])
            await communicator.send_json_to(
                {
                    "type": "message.send",
                    "payload": {"chat_id": private_chat.id, "text": "No access"},
                }
            )
            event = await self._receive_type(communicator, "error")
            self.assertEqual(event["code"], "forbidden")
            await communicator.disconnect()

        async_to_sync(scenario)()
