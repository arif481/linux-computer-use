"""Unit tests for cu.py. xdotool and the screen grab are faked; no X server needed."""
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "linux-computer-use", "scripts"))
import cu  # noqa: E402


class FakeXdotool:
    """Stands in for subprocess.run; records xdotool calls and answers queries."""

    def __init__(self, active="Untitled - Text Editor", cursor=(960, 540), fail_on=None):
        self.active = active
        self.cursor = cursor
        self.fail_on = fail_on
        self.calls = []

    def __call__(self, cmd, capture_output=True, text=True):
        args = cmd[1:]
        self.calls.append(args)
        if self.fail_on and args[0] == self.fail_on:
            return subprocess.CompletedProcess(cmd, 1, "", "simulated failure")
        out = ""
        if args[:2] == ["getmouselocation", "--shell"]:
            out = f"X={self.cursor[0]}\nY={self.cursor[1]}\nSCREEN=0\nWINDOW=42\n"
        elif args[:2] == ["getactivewindow", "getwindowname"]:
            out = self.active + "\n"
        return subprocess.CompletedProcess(cmd, 0, out, "")

    def commands(self, name):
        return [c for c in self.calls if c[0] == name]


def image_size(path):
    with Image.open(path) as img:
        return img.size


class CuTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = {"CU_DIR": self.tmp.name, "DISPLAY": ":99", "XDG_SESSION_TYPE": "x11"}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.x = FakeXdotool()
        patcher = mock.patch.object(cu.subprocess, "run", self.x)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(cu.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cu(self, *argv, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        patches = [contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)]
        if stdin is not None:
            patches.append(mock.patch.object(cu.sys, "stdin", io.StringIO(stdin)))
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            code = cu.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def set_scale(self, scale, screen=(1920, 1080)):
        cu.save_state({"scale": scale, "screen": list(screen)})


class ShotTests(CuTestCase):
    def grab_returns(self, size):
        return mock.patch.object(cu.ImageGrab, "grab", return_value=Image.new("RGB", size))

    def test_downscales_to_width_and_saves_scale(self):
        with self.grab_returns((1920, 1080)):
            code, out, _ = self.run_cu("shot")
        self.assertEqual(code, 0)
        path = out.splitlines()[0]
        self.assertEqual(image_size(path), (1280, 720))
        self.assertEqual(cu.load_state()["scale"], 1.5)
        self.assertIn("cursor=640,360", out)
        self.assertIn("active='Untitled - Text Editor'", out)

    def test_marks_cursor_in_red(self):
        with self.grab_returns((1920, 1080)):
            _, out, _ = self.run_cu("shot")
        with Image.open(out.splitlines()[0]) as shot:
            img = shot.convert("RGB")
        # The ring has radius 10 around (640, 360) in shot space.
        self.assertEqual(img.getpixel((649, 360)), (255, 0, 0))
        self.assertEqual(img.getpixel((100, 100)), (0, 0, 0))

    def test_small_screen_is_not_upscaled(self):
        with self.grab_returns((1024, 768)):
            _, out, _ = self.run_cu("shot")
        self.assertEqual(image_size(out.splitlines()[0]), (1024, 768))
        self.assertEqual(cu.load_state()["scale"], 1.0)

    def test_out_path(self):
        target = os.path.join(self.tmp.name, "custom.png")
        with self.grab_returns((800, 600)):
            self.run_cu("shot", "--out", target, "--grid", "100")
        self.assertTrue(os.path.exists(target))


class PointerTests(CuTestCase):
    def test_click_maps_shot_coords_to_screen(self):
        self.set_scale(1.5)
        code, _, _ = self.run_cu("click", "640", "360")
        self.assertEqual(code, 0)
        self.assertIn(["mousemove", "--sync", "960", "540"], self.x.calls)
        self.assertEqual(self.x.commands("click"),
                         [["click", "--repeat", "1", "--delay", "80", "1"]])

    def test_right_double_click(self):
        self.run_cu("click", "10", "10", "--button", "right", "--count", "2")
        self.assertEqual(self.x.commands("click"),
                         [["click", "--repeat", "2", "--delay", "80", "3"]])

    def test_without_state_scale_is_one(self):
        self.run_cu("move", "100", "200")
        self.assertIn(["mousemove", "--sync", "100", "200"], self.x.calls)

    def test_drag_moves_in_steps_and_releases(self):
        self.set_scale(2.0)
        self.run_cu("drag", "10", "10", "60", "10")
        self.assertEqual(self.x.calls[0], ["mousemove", "--sync", "20", "20"])
        self.assertEqual(self.x.calls[1], ["mousedown", "1"])
        self.assertEqual(self.x.calls[-2], ["mousemove", "120", "20"])
        self.assertEqual(self.x.calls[-1], ["mouseup", "1"])

    def test_drag_releases_button_after_error(self):
        fake = self.x

        def fail_midway(cmd, **kw):
            if cmd[1:3] == ["mousemove", "5"]:
                fake.calls.append(cmd[1:])
                return subprocess.CompletedProcess(cmd, 1, "", "boom")
            return fake(cmd, **kw)

        with mock.patch.object(cu, "DRAG_STEPS", 2), \
                mock.patch.object(cu.subprocess, "run", fail_midway):
            code, _, err = self.run_cu("drag", "0", "0", "10", "10")
        self.assertEqual(code, 1)
        self.assertIn("mousemove failed", err)
        self.assertEqual(self.x.calls[-1], ["mouseup", "1"])

    def test_scroll_at_point(self):
        self.set_scale(1.5)
        self.run_cu("scroll", "down", "3", "--x", "100", "--y", "100")
        self.assertIn(["mousemove", "--sync", "150", "150"], self.x.calls)
        self.assertEqual(self.x.commands("click"),
                         [["click", "--repeat", "3", "--delay", "30", "5"]])

    def test_scroll_needs_both_coordinates(self):
        code, _, err = self.run_cu("scroll", "up", "--x", "5")
        self.assertEqual(code, 1)
        self.assertIn("--x and --y", err)
        self.assertEqual(self.x.commands("click"), [])


class KeyboardTests(CuTestCase):
    def test_type_passes_text_after_double_dash(self):
        self.run_cu("type", "--", "-rf not an option")
        self.assertEqual(self.x.commands("type"),
                         [["type", "--delay", "12", "--", "-rf not an option"]])

    def test_into_refuses_other_window(self):
        self.x.active = "YouTube - Brave"
        code, _, err = self.run_cu("type", "hello", "--into", "Text Editor")
        self.assertEqual(code, 1)
        self.assertIn("refusing", err)
        self.assertEqual(self.x.commands("type"), [])

    def test_into_matches_case_insensitively(self):
        code, _, _ = self.run_cu("key", "ctrl+s", "--into", "text editor")
        self.assertEqual(code, 0)
        self.assertEqual(self.x.commands("key"), [["key", "--delay", "60", "ctrl+s"]])

    def test_into_refuses_when_no_window_is_active(self):
        self.x.active = ""
        code, _, _ = self.run_cu("key", "Return", "--into", "Editor")
        self.assertEqual(code, 1)
        self.assertEqual(self.x.commands("key"), [])

    def test_bad_regex_is_reported(self):
        code, _, err = self.run_cu("type", "x", "--into", "[oops")
        self.assertEqual(code, 1)
        self.assertIn("bad --into pattern", err)

    def test_stdin_drops_one_trailing_newline(self):
        self.run_cu("type", "-", stdin="line one\nline two\n")
        self.assertEqual(self.x.commands("type")[0][-1], "line one\nline two")


class ZoomTests(CuTestCase):
    def test_crops_at_full_resolution(self):
        self.set_scale(1.5)
        with mock.patch.object(cu.ImageGrab, "grab", return_value=Image.new("RGB", (150, 75))) as g:
            code, out, _ = self.run_cu("zoom", "100", "100", "100", "50")
        self.assertEqual(code, 0)
        self.assertEqual(g.call_args.kwargs["bbox"], (150, 150, 300, 225))
        self.assertEqual(image_size(out.splitlines()[0]), (300, 150))
        self.assertIn("(100 + px/3, 100 + py/3)", out)

    def test_clamps_to_screen_edge(self):
        self.set_scale(1.5)
        with mock.patch.object(cu.ImageGrab, "grab", return_value=Image.new("RGB", (120, 30))) as g:
            self.run_cu("zoom", "1200", "700", "200", "100")
        self.assertEqual(g.call_args.kwargs["bbox"], (1800, 1050, 1920, 1080))

    def test_off_screen_region_is_an_error(self):
        self.set_scale(1.5)
        code, _, err = self.run_cu("zoom", "2000", "2000", "10", "10")
        self.assertEqual(code, 1)
        self.assertIn("off screen", err)


class EnvironmentTests(CuTestCase):
    def test_wayland_is_refused_before_any_input(self):
        with mock.patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}):
            code, _, err = self.run_cu("click", "1", "1")
        self.assertEqual(code, 1)
        self.assertIn("Wayland", err)
        self.assertEqual(self.x.calls, [])

    def test_missing_display(self):
        with mock.patch.dict(os.environ, {"DISPLAY": ""}):
            code, _, err = self.run_cu("key", "a")
        self.assertEqual(code, 1)
        self.assertIn("DISPLAY", err)

    def test_missing_xdotool(self):
        with mock.patch.object(cu.subprocess, "run", side_effect=FileNotFoundError):
            code, _, err = self.run_cu("move", "1", "1")
        self.assertEqual(code, 1)
        self.assertIn("apt install xdotool", err)

    def test_invalid_numbers_are_rejected_by_argparse(self):
        for argv in (["click", "1", "1", "--count", "0"], ["scroll", "down", "-2"],
                     ["zoom", "0", "0", "1", "1", "--factor", "0"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    cu.main(argv)


class StateTests(CuTestCase):
    def test_corrupt_state_falls_back_to_scale_one(self):
        with open(os.path.join(self.tmp.name, "state.json"), "w") as f:
            f.write("{not json")
        self.assertEqual(cu.load_state(), {"scale": 1.0})

    def test_state_is_json(self):
        self.set_scale(1.25)
        with open(os.path.join(self.tmp.name, "state.json")) as f:
            self.assertEqual(json.load(f)["scale"], 1.25)

    def test_default_dir_is_private(self):
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.tmp.name}):
            del os.environ["CU_DIR"]
            path = cu.state_dir()
        self.assertEqual(path, os.path.join(self.tmp.name, f"claude-cu-{os.getuid()}"))
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o700)

    def test_default_dir_tightens_loose_permissions(self):
        path = os.path.join(self.tmp.name, f"claude-cu-{os.getuid()}")
        os.mkdir(path, 0o755)
        os.chmod(path, 0o755)
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.tmp.name}):
            del os.environ["CU_DIR"]
            cu.state_dir()
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o700)

    def test_default_dir_rejects_symlink(self):
        real = os.path.join(self.tmp.name, "elsewhere")
        os.mkdir(real)
        os.symlink(real, os.path.join(self.tmp.name, f"claude-cu-{os.getuid()}"))
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.tmp.name}):
            del os.environ["CU_DIR"]
            with self.assertRaises(cu.CuError):
                cu.state_dir()

    def test_clean_removes_only_images(self):
        for name in ("shot-1.png", "zoom-2.png"):
            open(os.path.join(self.tmp.name, name), "w").close()
        self.set_scale(1.0)
        with mock.patch.dict(os.environ, {"DISPLAY": ""}):  # clean works without X
            code, out, _ = self.run_cu("clean")
        self.assertEqual(code, 0)
        self.assertIn("removed 2", out)
        self.assertEqual(os.listdir(self.tmp.name), ["state.json"])


if __name__ == "__main__":
    unittest.main()
