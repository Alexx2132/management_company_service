"""Регрессии контроля доступа; только отдельная мигрированная БД с суффиксом _test."""
import asyncio
import io
import json
import os
import socket
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import uvicorn
from fastapi import HTTPException, UploadFile
from jose import jwt
from PIL import Image
from sqlalchemy import select
from starlette.datastructures import Headers
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.core.auth_validation import validate_password_value
from app.core.config import settings
from app.core.file_upload import validate_image_upload
from app.core.rate_limit import consume_auth_attempt
from app.core.security import create_access_token, generate_temporary_password, get_password_hash
from app.db.session import SessionLocal
from app.main import app
from app.models.location import Apartment, House, HouseEntrance
from app.models.message import MessageConversation, MessageParticipant
from app.models.password_recovery import PasswordRecoveryRequest
from app.models.push_device_token import PushDeviceToken
from app.models.ticket import Ticket
from app.models.ticket_complaint import ComplaintType, TicketComplaint
from app.models.user import User, UserRole
from app.services.live_update_hub import live_update_hub
from app.services.push_notification_service import PushNotificationService


def image_bytes():
    data = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(data, format="PNG")
    return data.getvalue()


class SecurityUnitTests(unittest.TestCase):
    def test_password_policy_and_random_defaults(self):
        passwords = {generate_temporary_password() for _ in range(100)}
        self.assertEqual(len(passwords), 100)
        for password in passwords:
            self.assertEqual(validate_password_value(password), password)
        for password in ["abc", "pass123", "a" * 73, "я" * 37]:
            with self.assertRaises(HTTPException):
                validate_password_value(password)
        self.assertEqual(validate_password_value("é" * 36), "é" * 36)

    def test_image_reencoding_removes_appended_content(self):
        data = image_bytes() + b"<script>secret-marker</script>"
        file = UploadFile(io.BytesIO(data), filename="photo.png", headers=Headers({"content-type": "image/png"}))
        extension, size = validate_image_upload(file)
        self.assertEqual(extension, "png")
        normalized = file.file.read()
        self.assertNotIn(b"secret-marker", normalized)
        self.assertEqual(size, len(normalized))
        Image.open(io.BytesIO(normalized)).verify()

    def test_push_binds_each_device_to_its_recipient(self):
        messaging = MagicMock()
        with patch.object(PushNotificationService, "_get_firebase_messaging", return_value=messaging):
            PushNotificationService._send_payload([(1, "test-device-a", 10), (2, "test-device-b", 20)],
                                                  {"title": "Test", "recipient_user_id": "spoofed"})
        calls = messaging.Message.call_args_list
        self.assertEqual([call.kwargs["data"]["recipient_user_id"] for call in calls], ["10", "20"])
        self.assertTrue(all("notification" not in call.kwargs for call in calls))


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "Нужна отдельная тестовая PostgreSQL")
class SecurityDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertTrue(settings.POSTGRES_DB.endswith("_test"))
        self.lifespan = app.router.lifespan_context(app)
        await self.lifespan.__aenter__()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        self.files = []
        self.suffix = uuid.uuid4().hex[:12]
        password_hash = await asyncio.to_thread(get_password_hash, "Initial-test-password")
        async with SessionLocal() as db:
            house = House(city="Security test", address=self.suffix)
            db.add(house)
            await db.flush()
            entrance = HouseEntrance(house_id=house.id, number=1)
            db.add(entrance)
            await db.flush()
            apartment = Apartment(house_id=house.id, entrance_id=entrance.id, floor_number=1, apartment_number="101")
            db.add(apartment)
            await db.flush()
            self.users = {}
            for label, role in [("admin", UserRole.ADMIN), ("assistant", UserRole.ADMIN_ASSISTANT),
                                ("dispatcher", UserRole.DISPATCHER), ("owner", UserRole.RESIDENT),
                                ("outsider", UserRole.RESIDENT)]:
                user = User(login=f"{label}-{self.suffix}", phone=f"{label}-{self.suffix}", full_name=f"Synthetic {label}",
                            contact_phone="+79000000001", role=role, password_hash=password_hash,
                            can_manage_password_recovery=label == "assistant")
                if label == "owner":
                    user.house_id, user.apartment_id, user.apartment = house.id, apartment.id, "101"
                db.add(user)
                self.users[label] = user
            await db.flush()
            self.ticket = Ticket(title="Synthetic ticket", author_id=self.users["owner"].id,
                                 house_id=house.id, apartment_id=apartment.id, apartment="101")
            db.add(self.ticket)
            await db.flush()
            self.complaint = TicketComplaint(ticket_id=self.ticket.id, author_id=self.users["owner"].id,
                                             complaint_type=ComplaintType.DISPATCHER_INACTION)
            db.add(self.complaint)
            await db.commit()
        self.headers = {key: {"Authorization": "Bearer " + create_access_token(user.id)} for key, user in self.users.items()}

    async def asyncTearDown(self):
        await self.client.aclose()
        for path in self.files:
            path = Path(path.lstrip("/")).resolve()
            if path.is_relative_to(Path("static/uploads").resolve()):
                path.unlink(missing_ok=True)
        await self.lifespan.__aexit__(None, None, None)

    async def request(self, method, path, role=None, expected=200, **kwargs):
        response = await self.client.request(method, path, headers=self.headers.get(role), **kwargs)
        self.assertEqual(response.status_code, expected, response.text)
        return response

    async def recovery(self, role):
        user = self.users[role]
        async with SessionLocal() as db:
            request = PasswordRecoveryRequest(requester_login=user.login, contact_phone=user.contact_phone,
                                              matched_user_id=user.id)
            db.add(request)
            await db.commit()
            return request.id

    async def test_public_recovery_response_is_identical_for_known_and_unknown_login(self):
        responses = []
        for login in [self.users["owner"].login, "missing-" + self.suffix]:
            response = await self.request("POST", "/api/v1/password-recovery/requests", expected=202,
                                          json={"login": login, "contact_phone": "+79999999999"})
            responses.append(response.json())
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(set(responses[0]), {"message"})

    async def test_assistant_cannot_reset_staff_password(self):
        for role in ["admin", "assistant", "dispatcher"]:
            recovery_id = await self.recovery(role)
            await self.request("POST", f"/api/v1/password-recovery/requests/{recovery_id}/reset",
                               role="assistant", expected=403, json={})

    async def test_reset_revokes_sessions_and_requires_different_password(self):
        async with SessionLocal() as db:
            device = PushDeviceToken(user_id=self.users["owner"].id, token="device-" + self.suffix,
                                     platform="android", role="resident", is_active=True)
            db.add(device)
            await db.commit()
            device_id = device.id
        recovery_id = await self.recovery("owner")
        reset = await self.request("POST", f"/api/v1/password-recovery/requests/{recovery_id}/reset",
                                   role="assistant", json={})
        temporary = reset.json()["temporary_password"]
        self.assertGreaterEqual(len(temporary), 12)
        self.assertNotEqual(temporary, "pass123")
        await self.request("GET", "/api/v1/users/me", "owner", expected=401)
        async with SessionLocal() as db:
            self.assertFalse((await db.get(PushDeviceToken, device_id)).is_active)
        login = await self.request("POST", "/api/v1/auth/login", data={"username": self.users["owner"].login, "password": temporary})
        self.headers["temporary"] = {"Authorization": "Bearer " + login.json()["access_token"]}
        profile = await self.request("GET", "/api/v1/users/me", "temporary")
        self.assertTrue(profile.json()["must_change_password"])
        await self.request("GET", "/api/v1/tickets/", "temporary", expected=403)
        await self.request("POST", "/api/v1/users/me/password", "temporary", expected=400,
                           json={"old_password": temporary, "new_password": temporary})
        await self.request("POST", "/api/v1/users/me/password", "temporary", expected=400,
                           json={"old_password": temporary, "new_password": "abc"})
        await self.request("POST", "/api/v1/users/me/password", "temporary",
                           json={"old_password": temporary, "new_password": "New-test-password"})
        await self.request("GET", "/api/v1/users/me", "temporary", expected=401)
        login = await self.request("POST", "/api/v1/auth/login", data={"username": self.users["owner"].login, "password": "New-test-password"})
        self.headers["fresh"] = {"Authorization": "Bearer " + login.json()["access_token"]}
        profile = await self.request("GET", "/api/v1/users/me", "fresh")
        self.assertFalse(profile.json()["must_change_password"])
        await self.request("GET", "/api/v1/tickets/", "fresh")

    async def test_legacy_complaints_enforce_same_permissions(self):
        for prefix in ["complaints", "ticket-complaints"]:
            listing = await self.request("GET", f"/api/v1/{prefix}/", "dispatcher")
            self.assertNotIn(self.complaint.id, [item["id"] for item in listing.json()])
            await self.request("PATCH", f"/api/v1/{prefix}/{self.complaint.id}/resolve", "dispatcher", expected=403,
                               json={"status": "DISMISSED", "resolution_comment": "Test"})
        await self.request("PATCH", f"/api/v1/complaints/{self.complaint.id}/resolve", "admin",
                           json={"status": "DISMISSED", "resolution_comment": "Test"})

    async def test_registration_generates_unique_passwords_and_requires_change(self):
        passwords = []
        for index in range(2):
            payload = {"login": f"registration-{index}-{self.suffix}", "full_name": "Synthetic resident",
                       "contact_phone": "+79000000002", "house_id": self.users["owner"].house_id,
                       "apartment_id": self.users["owner"].apartment_id}
            request = await self.request("POST", "/api/v1/registration/requests", json=payload)
            approved = await self.request("POST", f"/api/v1/registration/requests/{request.json()['id']}/approve",
                                          "admin", json={})
            passwords.append(approved.json()["temporary_password"])
            self.assertTrue(approved.json()["user"]["must_change_password"])
        self.assertNotEqual(passwords[0], passwords[1])
        self.assertTrue(all(len(value) >= 12 and value != "pass123" for value in passwords))

    async def test_uploads_and_attachment_access(self):
        for endpoint in [f"/api/v1/tickets/{self.ticket.id}/photos?kind=BEFORE",
                         f"/api/v1/ticket-complaints/{self.complaint.id}/photos"]:
            for filename, data, mime in [("test.html", b"<script>1</script>", "text/html"),
                                          ("test.jpg", b"<script>1</script>", "image/jpeg"),
                                          ("test.png", b"x" * (8 * 1024 * 1024 + 1), "image/png")]:
                await self.request("POST", endpoint, "owner", expected=400, files={"file": (filename, data, mime)})
            upload = await self.request("POST", endpoint, "owner", files={"file": ("photo.png", image_bytes(), "image/png")})
            path = upload.json()["file_path"]
            self.files.append(path)
            await self.request("GET", path, expected=401)
            await self.request("GET", path, "outsider", expected=403)
            photo = await self.request("GET", path, "owner")
            self.assertEqual(photo.headers["content-type"], "image/png")
            self.assertEqual(photo.headers["x-content-type-options"], "nosniff")
            self.assertIn("no-store", photo.headers["cache-control"])
            token = self.headers["owner"]["Authorization"].split(" ", 1)[1]
            cookie_photo = await self.client.get(path, headers={"Cookie": f"uk_token={token}"})
            self.assertEqual(cookie_photo.status_code, 200)
        await self.request("GET", "/static/uploads/settings/legacy.html", expected=404)

    async def test_login_throttle_and_atomic_shared_limit(self):
        for attempt in range(11):
            response = await self.request("POST", "/api/v1/auth/login", expected=401 if attempt < 10 else 429,
                                          data={"username": "absent-" + self.suffix, "password": "wrong"})
        self.assertGreater(int(response.headers["Retry-After"]), 0)
        async def consume():
            try:
                await consume_auth_attempt("test", self.suffix, 3, 60)
                return 200
            except HTTPException as error:
                return error.status_code
        statuses = await asyncio.gather(*(consume() for _ in range(10)))
        self.assertEqual(statuses.count(200), 3)
        self.assertEqual(statuses.count(429), 7)

    async def test_websocket_filters_events_origin_expiry_and_revocation(self):
        async with SessionLocal() as db:
            conversation = MessageConversation(created_by_id=self.users["owner"].id)
            db.add(conversation)
            await db.flush()
            db.add(MessageParticipant(conversation_id=conversation.id, user_id=self.users["owner"].id))
            await db.commit()
            conversation_id = conversation.id
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        url = f"ws://127.0.0.1:{port}/api/v1/ws/updates"
        try:
            for _ in range(100):
                if server.started:
                    break
                await asyncio.sleep(0.02)
            with self.assertRaises(InvalidStatus):
                async with connect(url, additional_headers=self.headers["owner"], origin="https://untrusted.invalid"):
                    pass
            expired = jwt.encode({"sub": str(self.users["owner"].id), "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
                                 settings.SECRET_KEY, algorithm=settings.ALGORITHM)
            with self.assertRaises(InvalidStatus):
                async with connect(url, additional_headers={"Authorization": "Bearer " + expired}):
                    pass
            async with connect(url, additional_headers=self.headers["owner"]) as owner, \
                    connect(url, additional_headers=self.headers["outsider"]) as outsider:
                for event in [{"entity": "message", "conversation_id": conversation_id},
                              {"entity": "ticket", "ticket_id": self.ticket.id},
                              {"entity": "complaint", "complaint_id": self.complaint.id}]:
                    await live_update_hub.broadcast(event)
                    self.assertEqual(json.loads(await asyncio.wait_for(owner.recv(), 2)), event)
                    # Pong служит границей: перед ним не должно быть чужих событий.
                    await outsider.send("ping")
                    self.assertEqual(await asyncio.wait_for(outsider.recv(), 2), "pong")
                await self.request("POST", "/api/v1/users/me/password", "owner",
                                   json={"old_password": "Initial-test-password", "new_password": "Changed-test-password"})
                await owner.send("ping")
                with self.assertRaises(ConnectionClosed):
                    await asyncio.wait_for(owner.recv(), 2)
        finally:
            server.should_exit = True
            await asyncio.wait_for(serving, 5)
            listener.close()
