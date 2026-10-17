import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from dashboard_server import token_worker_key


class WorkerReconnectTests(unittest.TestCase):
    def test_backoff_grows_and_caps_without_exposing_token(self):
        with patch.object(app.random, "uniform", side_effect=lambda low, high: high):
            self.assertEqual(app.worker_reconnect_delay(1), 4.0)
            self.assertEqual(app.worker_reconnect_delay(2), 8.0)
            self.assertEqual(app.worker_reconnect_delay(3), 16.0)
            self.assertEqual(app.worker_reconnect_delay(100), 90.0)

        token = "private-token-value"
        key = token_worker_key(token)
        self.assertEqual(key, token_worker_key(token))
        self.assertTrue(key.startswith("token:"))
        self.assertNotIn(token, key)


class WorkerCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_bot_start_waits_for_stop_to_finish(self):
        original_running = app.bot_state.bot_running
        stop_entered = asyncio.Event()
        allow_stop_to_finish = asyncio.Event()
        start_running_states = []

        async def fake_stop():
            stop_entered.set()
            await allow_stop_to_finish.wait()
            app.bot_state.bot_running = False
            return 0

        def fake_start():
            start_running_states.append(app.bot_state.bot_running)
            app.bot_state.bot_running = True
            return 1

        try:
            with (
                patch.object(app, "_stop_all_account_workers_unlocked", new=fake_stop),
                patch.object(app, "_start_all_account_workers_unlocked", new=fake_start),
            ):
                stopping = asyncio.create_task(app.stop_all_account_workers())
                await asyncio.wait_for(stop_entered.wait(), timeout=2)
                starting = asyncio.create_task(app.start_all_account_workers())
                await asyncio.sleep(0)
                self.assertEqual(start_running_states, [])

                allow_stop_to_finish.set()
                await asyncio.gather(stopping, starting)

            self.assertEqual(start_running_states, [False])
            self.assertTrue(app.bot_state.bot_running)
        finally:
            app.bot_state.bot_running = original_running

    async def test_cancelled_worker_awaits_all_background_tasks(self):
        child_tasks = []
        children_started = asyncio.Event()
        start_count = 0

        async def block_until_cancelled(*_args, **_kwargs):
            nonlocal start_count
            child_tasks.append(asyncio.current_task())
            start_count += 1
            if start_count == 3:
                children_started.set()
            await asyncio.Event().wait()

        async def keep_game_open(*_args, **_kwargs):
            await asyncio.Event().wait()

        original_credentials = app.bot_state.account_credentials
        app.bot_state.account_credentials = {
            "account-1": {"account_id": "account-1"}
        }
        account_data = {
            "account_id": "account-1",
            "token": "test-token",
            "server_time": 0,
            "aes_ak": b"0" * 16,
            "iv_i": b"1" * 16,
            "region": "IND",
            "release_version": "test",
            "client_version": "test",
            "informational_addrs": [],
            "functional_addrs": [],
        }

        try:
            with (
                patch.object(app, "wait_for_all_saved_accounts_in_clan", new=AsyncMock()),
                patch.object(app, "build_tcp_startup_packet", new=AsyncMock(return_value=b"packet")),
                patch.object(app, "informational", new=block_until_cancelled),
                patch.object(app, "ping_worker", new=block_until_cancelled),
                patch.object(app, "refresh_account_profile", new=block_until_cancelled),
                patch.object(app, "functional_battle_royale", new=keep_game_open),
                patch.object(app, "ENABLE_HTTP_PING", True),
            ):
                worker = asyncio.create_task(app.run_account_worker(account_data, "account-1"))
                await asyncio.wait_for(children_started.wait(), timeout=2)
                worker.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(worker, timeout=2)

            self.assertEqual(len(child_tasks), 3)
            self.assertTrue(all(task.done() for task in child_tasks))
        finally:
            app.bot_state.account_credentials = original_credentials


class ClanMembershipGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_skip_setting_continues_without_loading_or_checking_roster(self):
        account_id = "test-skip-clan-check"
        with (
            patch.object(
                app,
                "load_clan_config",
                return_value={
                    "clan_id": "",
                    "region": "IND",
                    "skip_clan_check": True,
                },
            ),
            patch.object(app, "load_accounts") as load_accounts,
            patch.object(app, "_get_clan_member_ids", new=AsyncMock()) as get_members,
            patch.object(app.bot_state, "update_status") as update_status,
            patch.object(app.bot_state, "log") as log,
        ):
            await app.wait_for_all_saved_accounts_in_clan(account_id)

        load_accounts.assert_not_called()
        get_members.assert_not_awaited()
        update_status.assert_called_once_with(account_id, "ONLINE", 0)
        log.assert_called_once()
        app._clan_gate_skip_logged.discard(account_id)


if __name__ == "__main__":
    unittest.main()
