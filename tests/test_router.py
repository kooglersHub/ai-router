import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from router.agents import AgentRegistry, run_command
from router.service import Router


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "Projekt mit Leerzeichen"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        (self.repo / "README.md").write_text("# Test\n", encoding="utf-8")
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@localhost",
            "commit",
            "-m",
            "initial",
        )
        self.router = Router(self.root / "state", self.repo)

    def tearDown(self):
        self.router.close()
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def payload(self, **changes):
        data = dict(
            title="Suche reparieren",
            description="Filter korrigieren",
            criteria="Tests bestehen",
            repo=str(self.repo),
            agent="auto",
            mode="demo",
            task_type="bugfix",
            difficulty="medium",
        )
        return data | changes

    def wait(self, task_id):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            task = self.router.task(task_id)
            if task["status"] not in ("queued", "running", "checking"):
                return task
            time.sleep(0.02)
        self.fail("Task did not finish")

    def test_demo_never_invokes_agent_or_changes_repository(self):
        task = self.router.create(self.payload())
        result = self.wait(task["id"])
        self.assertEqual(result["status"], "demo_complete")
        self.assertIsNone(result["cost_actual"])
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(result["test_status"], "not_run")

    def test_live_requires_explicit_consent(self):
        with self.assertRaisesRegex(ValueError, "Freigabe"):
            self.router.create(self.payload(mode="live", agent="codex"))

    def test_freebuff_creates_isolated_worktree_and_waits_for_user(self):
        task = self.router.create(
            self.payload(mode="live", agent="freebuff", consent=True)
        )
        result = self.wait(task["id"])
        self.assertEqual(result["status"], "handoff")
        self.assertTrue(Path(result["worktree"]).is_dir())
        self.assertEqual(self.git("branch", "--show-current").strip(), "main")
        self.assertEqual(self.git("status", "--porcelain"), "")
        with self.assertRaisesRegex(ValueError, "aktive"):
            self.router.create(self.payload())

    def test_review_includes_untracked_file_and_does_not_claim_tests_passed(self):
        task = self.wait(
            self.router.create(
                self.payload(mode="live", agent="freebuff", consent=True)
            )["id"]
        )
        (Path(task["worktree"]) / "hello.txt").write_text("Hallo\n", encoding="utf-8")
        self.router.review(task["id"])
        result = self.wait(task["id"])
        self.assertEqual(result["status"], "review")
        self.assertIn("hello.txt", result["files"])
        self.assertIn("Hallo", result["diff"])
        self.assertEqual(result["test_status"], "not_run")

    def test_restart_marks_active_task_interrupted(self):
        task = self.wait(
            self.router.create(
                self.payload(mode="live", agent="freebuff", consent=True)
            )["id"]
        )
        self.router.close()
        self.router = Router(self.root / "state", self.repo)
        self.assertEqual(self.router.task(task["id"])["status"], "interrupted")

    def test_path_and_input_validation(self):
        for changes in (
            {"repo": str(self.root)},
            {"title": ""},
            {"agent": "unknown"},
            {"mode": "invalid"},
            {"budget": -1},
            {"timeout": 0},
            {"consent": "yes", "mode": "live"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.router.create(self.payload(**changes))

    def test_timeout_stops_process(self):
        with self.assertRaises(TimeoutError):
            run_command(
                [sys.executable, "-c", "import time; time.sleep(30)"], self.repo, 0.1
            )

    def test_registry_does_not_invent_freebuff_headless_flags(self):
        registry = AgentRegistry(self.root)
        agent = next(item for item in registry.list() if item["id"] == "freebuff")
        self.assertEqual(agent["kind"], "interactive")
        self.assertEqual(
            registry.choose("auto", "bugfix", "medium", {"codex": 0, "gemini": 0}),
            "freebuff",
        )

    def test_automatic_execution_collects_diff_and_runs_tests_only_on_request(self):
        self.router.save_settings(
            {"tests": [[sys.executable, "-c", 'print("test passed")']]}
        )
        script = 'from pathlib import Path; Path("change.txt").write_text("actual subprocess change")'
        with (
            patch.object(
                self.router.registry, "command", return_value=[sys.executable]
            ),
            patch.object(
                self.router.registry,
                "execution",
                return_value=[sys.executable, "-c", script],
            ),
        ):
            task = self.wait(
                self.router.create(
                    self.payload(mode="live", agent="codex", consent=True)
                )["id"]
            )
        self.assertEqual(task["status"], "review")
        self.assertIn("change.txt", task["files"])
        self.assertEqual(task["test_status"], "not_run")
        self.router.review(task["id"], run_tests=True)
        result = self.wait(task["id"])
        self.assertEqual(result["test_status"], "passed")
        self.assertIn("test passed", result["test_results"][0]["output"])
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_failed_test_is_preserved_as_failure(self):
        self.router.save_settings(
            {"tests": [[sys.executable, "-c", "raise SystemExit(2)"]]}
        )
        task = self.wait(
            self.router.create(
                self.payload(mode="live", agent="freebuff", consent=True)
            )["id"]
        )
        self.router.review(task["id"], run_tests=True)
        result = self.wait(task["id"])
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["test_status"], "failed")

    def test_second_process_cannot_recover_active_instance(self):
        with self.assertRaisesRegex(RuntimeError, "bereits"):
            Router(self.root / "state", self.repo)

    def test_auto_routing_respects_difficulty_and_budget_before_selection(self):
        self.router.save_settings(
            {"estimated_costs": {"codex": 2, "gemini": 0.1, "freebuff": 0}}
        )
        with (
            patch.object(
                self.router.registry, "command", return_value=[sys.executable]
            ),
            patch.object(
                self.router.registry,
                "execution",
                return_value=[sys.executable, "-c", "pass"],
            ),
        ):
            task = self.wait(
                self.router.create(
                    self.payload(mode="live", agent="auto", consent=True, budget=0.2)
                )["id"]
            )
        self.assertEqual(task["agent"], "gemini")
        with patch.object(
            self.router.registry, "command", return_value=[sys.executable]
        ):
            self.assertEqual(
                self.router.registry.choose("auto", "feature", "easy", {}), "gemini"
            )

    def test_settings_reject_shell_strings_and_invalid_quota(self):
        for value in (
            {"tests": ["python -m pytest"]},
            {"quotas": {"codex": -1}},
            {"quotas": {"codex": 1.5}},
            {"estimated_costs": {"codex": float("nan")}},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.router.save_settings(value)

    def test_tests_added_after_creation_can_be_run(self):
        task = self.wait(
            self.router.create(
                self.payload(mode="live", agent="freebuff", consent=True)
            )["id"]
        )
        self.router.save_settings(
            {"tests": [[sys.executable, "-c", 'print("new test configuration")']]}
        )
        self.router.review(task["id"], run_tests=True)
        result = self.wait(task["id"])
        self.assertEqual(result["test_status"], "passed")
        self.assertIn("new test configuration", result["test_results"][0]["output"])

    def test_timeout_preserves_diagnostic_output(self):
        try:
            run_command(
                [
                    sys.executable,
                    "-u",
                    "-c",
                    'import time; print("before timeout",flush=True); time.sleep(30)',
                ],
                self.repo,
                0.2,
            )
        except TimeoutError as error:
            self.assertIn("before timeout", error.output)
        else:
            self.fail("Expected timeout")

    def test_restart_keeps_running_freebuff_session_guarded(self):
        task = self.wait(
            self.router.create(
                self.payload(mode="live", agent="freebuff", consent=True)
            )["id"]
        )
        self.router.update(
            task["id"], terminal_pid=12345, terminal_identity="verified-start-time"
        )
        self.router.close()
        with patch(
            "router.service.process_identity", return_value="verified-start-time"
        ):
            self.router = Router(self.root / "state", self.repo)
            self.assertEqual(self.router.task(task["id"])["status"], "handoff")
            with self.assertRaisesRegex(ValueError, "sitzung"):
                self.router.review(task["id"])
            with self.assertRaisesRegex(ValueError, "aktive"):
                self.router.create(self.payload())

    def test_missing_test_executable_does_not_keep_previous_pass(self):
        task = self.wait(
            self.router.create(
                self.payload(mode="live", agent="freebuff", consent=True)
            )["id"]
        )
        self.router.save_settings({"tests": [[sys.executable, "-c", "pass"]]})
        self.router.review(task["id"], run_tests=True)
        self.assertEqual(self.wait(task["id"])["test_status"], "passed")
        self.router.save_settings(
            {"tests": [["router-definitely-missing-test-executable"]]}
        )
        self.router.review(task["id"], run_tests=True)
        result = self.wait(task["id"])
        self.assertEqual(result["test_status"], "failed")
        self.assertIsNone(result["test_results"][0]["exit_code"])


if __name__ == "__main__":
    unittest.main()
