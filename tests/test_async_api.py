import asyncio
import base64
import csv
import io
import inspect as python_inspect
import os
import socket
import unittest
import uuid
from pathlib import Path

import httpx
import uvicorn
from websockets.asyncio.client import connect
from sqlalchemy import delete, inspect, select, text

from app.cli.create_admin import create_admin
from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.operations import run_db
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.user import User, UserRole
from app.models.auth_rate_limit import AuthRateLimit
from app.services.live_update_hub import live_update_hub


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "Set RUN_DB_TESTS=1 with a separate migrated test database")
class AsyncDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertTrue(settings.POSTGRES_DB.endswith("_test"), "Tests require an isolated database ending in _test")
        async with SessionLocal() as db:
            await db.execute(delete(AuthRateLimit))
            await db.commit()
        self.lifespan = app.router.lifespan_context(app)
        await self.lifespan.__aenter__()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        self.files = []

    async def asyncTearDown(self):
        await self.client.aclose()
        for file_path in self.files:
            path = Path(file_path.lstrip("/"))
            if path.is_relative_to(Path("static")):
                path.unlink(missing_ok=True)
        await self.lifespan.__aexit__(None, None, None)

    async def request(self, method, path, headers=None, expected=200, **kwargs):
        response = await self.client.request(method, path, headers=headers, **kwargs)
        self.assertEqual(response.status_code, expected, f"{method} {path}: {response.text}")
        return response.json() if response.content else None

    async def login(self, login, password="test-pass-123"):
        result = await self.request("POST", "/api/v1/auth/login", data={"username": login, "password": password})
        return {"Authorization": f"Bearer {result['access_token']}"}

    async def test_database_io_yields_to_event_loop(self):
        async with SessionLocal() as db:
            self.assertEqual(await db.scalar(text("SHOW TIMEZONE")), "UTC")
            task = asyncio.create_task(run_db(db, lambda session: session.execute(text("SELECT pg_sleep(0.35)"))))
            ticks = 0
            while not task.done():
                await asyncio.sleep(0.02)
                ticks += 1
            await task
            self.assertGreater(ticks, 4)

    async def test_websocket_auth_releases_database_connection(self):
        async with SessionLocal() as db:
            admin_id = await db.scalar(select(User.id).where(User.role == UserRole.ADMIN))
        if admin_id is None:
            admin_id = await create_admin("deployment-admin", "test-pass-123", "Deployment administrator")
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            for _ in range(100):
                if server.started:
                    break
                await asyncio.sleep(0.02)
            self.assertTrue(server.started)
            async with connect(f"ws://127.0.0.1:{port}/api/v1/ws/updates", additional_headers={
                "Cookie": f"uk_token={create_access_token(admin_id)}",
            }) as websocket:
                self.assertEqual(engine.pool.checkedout(), 0)
                await websocket.send("ping")
                self.assertEqual(await asyncio.wait_for(websocket.recv(), timeout=2), "pong")
                await live_update_hub.broadcast({"entity": "notification", "user_id": admin_id, "event": "test-update"})
                self.assertIn("test-update", await asyncio.wait_for(websocket.recv(), timeout=2))
        finally:
            server.should_exit = True
            await asyncio.wait_for(serving, timeout=5)
            listener.close()

    async def test_schema_and_api_workflows(self):
        async with engine.connect() as connection:
            def missing_columns(conn):
                inspector = inspect(conn)
                missing = []
                for table in Base.metadata.sorted_tables:
                    if not inspector.has_table(table.name):
                        missing.append(table.name)
                        continue
                    actual = {column["name"] for column in inspector.get_columns(table.name)}
                    missing.extend(f"{table.name}.{column.name}" for column in table.columns if column.name not in actual)
                return missing
            self.assertEqual(await connection.run_sync(missing_columns), [])

        async with SessionLocal() as db:
            admin_id = await db.scalar(select(User.id).where(User.role == UserRole.ADMIN))
        if admin_id is None:
            admin_id = await create_admin("deployment-admin", "test-pass-123", "Deployment administrator")
        with self.assertRaises(ValueError):
            await create_admin("another-admin", "test-pass-123", "Duplicate administrator")
        admin = await self.login("deployment-admin")
        await self.request("POST", "/api/v1/auth/login", expected=401, data={"username": "deployment-admin", "password": "wrong"})
        await self.request("GET", "/api/v1/users/me", expected=401, headers={"Authorization": f"Bearer {create_access_token('not-a-user-id')}"})

        specification = app.openapi()
        for path, methods in specification["paths"].items():
            if "get" not in methods or "{" in path:
                continue
            if any(parameter.get("required") for parameter in methods["get"].get("parameters", [])):
                continue
            response = await self.client.get(path, headers=admin)
            self.assertLess(response.status_code, 500, f"GET {path}: {response.text}")
        for route in app.routes:
            if hasattr(route, "dependant") and any(dependency.name == "db" for dependency in route.dependant.dependencies):
                self.assertTrue(python_inspect.iscoroutinefunction(route.endpoint), route.path)

        suffix = uuid.uuid4().hex[:10]
        house = await self.request("POST", "/api/v1/houses/with-structure", headers=admin, json={
            "city": "Test city", "address": f"Test street {suffix}",
            "entrances": [{"number": 1, "floors_count": 1, "apartments_per_floor": 2}],
        })
        apartment = house["entrances"][0]["apartments"][0]
        resident = await self.request("POST", "/api/v1/users/", headers=admin, json={
            "full_name": "Test resident", "login": f"resident-{suffix}", "password": "test-pass-123",
            "contact_phone": "+79001234567", "role": "resident", "house_id": house["id"], "apartment_id": apartment["id"],
        })
        resident_headers = await self.login(resident["login"])
        other = await self.request("POST", "/api/v1/users/", headers=admin, json={
            "full_name": "Other resident", "login": f"other-{suffix}", "password": "test-pass-123",
            "contact_phone": "+79001234568", "role": "resident", "house_id": house["id"], "apartment_id": house["entrances"][0]["apartments"][1]["id"],
        })
        await self.request("POST", "/api/v1/messages/conversations", headers=resident_headers, expected=403, json={"participant_id": other["id"]})
        await self.request("GET", "/api/v1/users/", headers=resident_headers, expected=403)
        await self.request("POST", "/api/v1/users/", headers=admin, expected=400, json={
            "full_name": "Duplicate login", "login": resident["login"], "password": "test-pass-123", "role": "resident",
        })

        specialty = await self.request("POST", "/api/v1/executors/specialties", headers=admin, json={"code": f"test-{suffix}", "name": f"Test specialty {suffix}"})
        executors = []
        for number in (1, 2):
            executor = await self.request("POST", "/api/v1/executors/", headers=admin, json={
                "first_name": f"Executor{number}", "last_name": "Test", "login": f"executor{number}-{suffix}",
                "password": "test-pass-123", "specialty_ids": [specialty["id"]], "primary_specialty_id": specialty["id"],
            })
            await self.request("PUT", f"/api/v1/executors/{executor['id']}/schedules", headers=admin, json=[
                {"weekday": day, "work_start": "00:00:00", "work_end": "23:59:59", "is_active": True} for day in range(7)
            ])
            executors.append((executor, await self.login(executor["user"]["login"])))

        categories = await self.request("GET", "/api/v1/categories/?category_type=location", headers=admin)
        place = next(item for item in categories if item["category_type"] == "location")
        category = await self.request("POST", "/api/v1/categories/", headers=admin, json={"name": f"Test problem {suffix}", "category_type": "problem"})
        ticket = await self.request("POST", "/api/v1/tickets/", headers=resident_headers, json={
            "title": "Test problem", "description": "Please repair the issue", "category_id": category["id"], "place_category_id": place["id"],
        })
        ticket_path = f"/api/v1/tickets/{ticket['id']}"
        export = await self.client.get("/api/v1/reports/attention-tickets/export.csv", headers=admin)
        self.assertEqual(export.status_code, 200)
        exported = next(row for row in csv.DictReader(io.StringIO(export.text)) if row["ticket_id"] == str(ticket["id"]))
        self.assertEqual(exported["status"], "created")
        self.assertEqual(exported["first_response_overdue"], "False")
        await self.request("POST", ticket_path + "/photos?kind=AFTER", headers=resident_headers, expected=403, files={"file": ("wrong.png", b"image", "image/png")})
        await self.request("GET", ticket_path, expected=403, headers=await self.login(other["login"]))
        for index, (executor, executor_headers) in enumerate(executors):
            await self.request("PATCH", ticket_path + "/assign", headers=admin, json={"executor_id": executor["user_id"]})
            await self.request("PATCH", ticket_path + "/status", headers=executor_headers, json={"status": "in_progress", "comment": "Arriving shortly"})
            await self.request("PATCH", ticket_path + "/status", headers=executor_headers, expected=400, json={"status": "done"})
            photo = await self.request("POST", ticket_path + "/photos?kind=AFTER", headers=executor_headers, files={
                "file": ("report.png", base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9ZkAAAAASUVORK5CYII="), "image/png"),
            })
            self.files.append(photo["file_path"])
            await self.request("DELETE", f"/api/v1/tickets/photos/{photo['id']}", headers=resident_headers, expected=403)
            if index == 1:
                previous_headers = executors[0][1]
                await self.request("DELETE", f"/api/v1/tickets/photos/{photo['id']}", headers=previous_headers, expected=403)
                await self.request("POST", ticket_path + "/photos?kind=AFTER", headers=previous_headers, expected=403, files={"file": ("wrong.png", b"image", "image/png")})
                await self.request("PATCH", ticket_path + "/status", headers=previous_headers, expected=403, json={"status": "done"})
            await self.request("PATCH", ticket_path + "/status", headers=executor_headers, json={"status": "done", "comment": "Work completed"})
            if index == 0:
                complaint = await self.request("POST", "/api/v1/ticket-complaints/", headers=resident_headers, json={
                    "ticket_id": ticket["id"], "complaint_type": "QUALITY", "description": "The issue remains",
                })
                await self.request("PATCH", ticket_path + "/status", headers=resident_headers, expected=400, json={"status": "closed", "resident_rating": 5})
                await self.request("PATCH", f"/api/v1/ticket-complaints/{complaint['id']}/resolve", headers=admin, json={
                    "status": "RESOLVED", "resolution_comment": "Please repeat the work",
                })
        closed = await self.request("PATCH", ticket_path + "/status", headers=resident_headers, json={"status": "closed", "comment": "Thank you", "resident_rating": 5})
        self.assertEqual(closed["status"], "closed")
        first, first_headers = executors[0]
        historical = await self.request("GET", ticket_path, headers=first_headers)
        self.assertTrue(historical["historical_executor_view"])
        history = await self.request("GET", ticket_path + "/history", headers=first_headers)
        self.assertFalse(any(item["user_id"] == executors[1][0]["user_id"] for item in history))
        await self.request("POST", ticket_path + "/executor-reviews", headers=resident_headers, json={"executor_id": first["user_id"], "rating": 2, "review_text": "The first repair was incomplete"})
        await self.request("POST", ticket_path + "/executor-reviews", headers=resident_headers, expected=409, json={"executor_id": first["user_id"], "rating": 5})
