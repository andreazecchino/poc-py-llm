import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main


def make_fake_chunks(pieces):
    async def gen():
        for piece in pieces:
            yield SimpleNamespace(message=SimpleNamespace(content=piece))

    return gen()


async def fake_chat_success(*args, **kwargs):
    return make_fake_chunks(["Hello", ", world!"])


async def fake_chat_error(*args, **kwargs):
    raise RuntimeError("ollama unreachable")


class MainTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        main.sessions.clear()

    def tearDown(self):
        main.sessions.clear()

    def create_session(self, system=None):
        body = {"system": system} if system is not None else {}
        response = self.client.post("/sessions", json=body)
        self.assertEqual(response.status_code, 201)
        return response.json()["session_id"]

    def test_health_check_healthy(self):
        with patch.object(main.ollama_client, "list", new=AsyncMock(return_value=None)):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["services"]["ollama"], "online")

    def test_health_check_unhealthy(self):
        with patch.object(
            main.ollama_client, "list", new=AsyncMock(side_effect=Exception("down"))
        ):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)

    def test_session_lifecycle(self):
        session_id = self.create_session()

        get_response = self.client.get(f"/sessions/{session_id}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json(), [])

        delete_response = self.client.delete(f"/sessions/{session_id}")
        self.assertEqual(delete_response.status_code, 204)

        after_delete = self.client.get(f"/sessions/{session_id}")
        self.assertEqual(after_delete.status_code, 404)

    def test_create_session_with_system_prompt(self):
        session_id = self.create_session(system="You are terse.")

        messages = self.client.get(f"/sessions/{session_id}").json()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "You are terse.")

    def test_generate_unknown_session_returns_404(self):
        with patch.object(main.ollama_client, "chat", side_effect=fake_chat_success) as chat_mock:
            response = self.client.post(
                "/generate", json={"session_id": "does-not-exist", "text": "hi"}
            )
        self.assertEqual(response.status_code, 404)
        chat_mock.assert_not_called()

    def test_generate_happy_path_streams_and_updates_history(self):
        session_id = self.create_session()

        with patch.object(main.ollama_client, "chat", side_effect=fake_chat_success):
            response = self.client.post(
                "/generate", json={"session_id": session_id, "text": "Hello"}
            )

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("event: message", body)
        self.assertIn('"content": "Hello"', body)
        self.assertIn("event: done", body)

        messages = self.client.get(f"/sessions/{session_id}").json()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0], {"role": "user", "content": "Hello"})
        self.assertEqual(messages[1], {"role": "assistant", "content": "Hello, world!"})

    def test_generate_error_path_does_not_append_assistant_message(self):
        session_id = self.create_session()

        with patch.object(main.ollama_client, "chat", side_effect=fake_chat_error):
            response = self.client.post(
                "/generate", json={"session_id": session_id, "text": "Hello"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: error", response.text)

        messages = self.client.get(f"/sessions/{session_id}").json()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")


if __name__ == "__main__":
    unittest.main()
