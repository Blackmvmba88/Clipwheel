import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cleepwheel import mouse


class MouseListenerTest(unittest.TestCase):
    @patch("cleepwheel.mouse.subprocess.Popen")
    def test_spawn_window_uses_same_database_and_gui_command(self, popen):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            mouse._spawn_window(db)

        command = popen.call_args.args[0]
        self.assertEqual(command[1:3], ["-m", "cleepwheel"])
        self.assertEqual(command[-3:], ["--db", str(db), "warm-window"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertTrue(callable(popen.call_args.kwargs["preexec_fn"]))

    @patch("cleepwheel.mouse.os.kill")
    @patch("cleepwheel.mouse.time.perf_counter", side_effect=[1.0, 1.0002])
    def test_wake_window_uses_signal_without_spawning(self, _clock, kill):
        process = unittest.mock.Mock(pid=4321)

        elapsed_ms = mouse._wake_window(process)

        kill.assert_called_once_with(4321, mouse.signal.SIGUSR1)
        self.assertAlmostEqual(elapsed_ms, 0.2)

    @patch("cleepwheel.mouse.ctypes.CDLL", side_effect=OSError("missing"))
    def test_framework_load_failure_is_actionable(self, _cdll):
        with self.assertRaisesRegex(mouse.MouseListenerError, "failed to load"):
            mouse._load_quartz()
