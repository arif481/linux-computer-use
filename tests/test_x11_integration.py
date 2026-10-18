"""End-to-end tests against a real X server.

Needs an X display with a window manager (for _NET_ACTIVE_WINDOW), xdotool,
Pillow and Tk. CI runs them under Xvfb with openbox:

    CU_INTEGRATION=1 xvfb-run -a -s "-screen 0 1920x1080x24" \
        sh -c 'openbox & sleep 2; python3 -m unittest discover -s tests -v'

Skipped unless CU_INTEGRATION=1, so they never touch a real desktop by accident.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CU = os.path.join(ROOT, "skills", "linux-computer-use", "scripts", "cu.py")
APP = os.path.join(ROOT, "tests", "x11_target_app.py")
TITLE = "cu-test-target"


@unittest.skipUnless(os.environ.get("CU_INTEGRATION") == "1",
                     "set CU_INTEGRATION=1 under a disposable X server with a window manager")
class X11IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.log = os.path.join(cls.tmp, "events.log")
        cls.env = dict(os.environ, CU_DIR=cls.tmp, XDG_SESSION_TYPE="x11")
        cls.app = subprocess.Popen([sys.executable, APP, cls.log])
        out = subprocess.run(["xdotool", "search", "--sync", "--onlyvisible", "--name", TITLE],
                             capture_output=True, text=True, timeout=20, check=True)
        cls.wid = out.stdout.split()[-1]
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.app.terminate()
        cls.app.wait(timeout=10)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.cu("focus", TITLE)
        self.cu("shot")
        self.scale = float(self.state_line("scale"))

    # --- helpers ---

    def cu(self, *args, check=True):
        r = subprocess.run([sys.executable, CU, *args], env=self.env,
                           capture_output=True, text=True, timeout=30)
        if check:
            self.assertEqual(r.returncode, 0, f"cu.py {' '.join(args)} failed: {r.stderr}")
        return r

    def state_line(self, key):
        import json
        with open(os.path.join(self.tmp, "state.json")) as f:
            return json.load(f)[key]

    def events(self):
        with open(self.log) as f:
            return f.read().splitlines()

    def wait_for(self, predicate, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            matches = [e for e in self.events() if predicate(e)]
            if matches:
                return matches
            time.sleep(0.1)
        self.fail(f"no matching event; log was: {self.events()}")

    def canvas_point(self, dx, dy):
        """Real screen pixel inside the canvas, offset from the window's centre."""
        out = subprocess.run(["xdotool", "getwindowgeometry", "--shell", self.wid],
                             capture_output=True, text=True, check=True).stdout
        g = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
        return int(g["X"]) + int(g["WIDTH"]) // 2 + dx, int(g["Y"]) + int(g["HEIGHT"]) // 2 + dy

    def shot_coords(self, x, y):
        return f"{x / self.scale:.4f}", f"{y / self.scale:.4f}"

    def assert_near(self, event, kind, x, y):
        _, ex, ey = event.split()
        self.assertEqual(event.split()[0], kind)
        self.assertLessEqual(abs(int(ex) - x), 1, event)
        self.assertLessEqual(abs(int(ey) - y), 1, event)

    # --- tests ---

    def test_shot_reports_size_and_active_window(self):
        r = self.cu("shot")
        path, info = r.stdout.splitlines()
        self.assertTrue(os.path.exists(path))
        self.assertIn("size=1280x", info)
        self.assertIn(f"active='{TITLE}'", info)

    def test_click_lands_on_mapped_pixel(self):
        x, y = self.canvas_point(-50, 60)
        self.cu("click", *self.shot_coords(x, y))
        press = self.wait_for(lambda e: e.startswith("press"))[-1]
        self.assert_near(press, "press", x, y)

    def test_right_click(self):
        x, y = self.canvas_point(40, 40)
        self.cu("click", *self.shot_coords(x, y), "--button", "right")
        self.assert_near(self.wait_for(lambda e: e.startswith("right"))[-1], "right", x, y)

    def test_drag_releases_at_target(self):
        x1, y1 = self.canvas_point(-100, 50)
        x2, y2 = self.canvas_point(100, 100)
        self.cu("drag", *self.shot_coords(x1, y1), *self.shot_coords(x2, y2))
        self.assert_near(self.wait_for(lambda e: e.startswith("release"))[-1], "release", x2, y2)

    def test_scroll(self):
        before = len([e for e in self.events() if e == "scroll down"])
        x, y = self.canvas_point(0, 80)
        self.cu("scroll", "down", "2", "--x", self.shot_coords(x, y)[0],
                "--y", self.shot_coords(x, y)[1])
        self.wait_for(lambda e: e == "scroll down")
        time.sleep(0.3)
        self.assertEqual(len([e for e in self.events() if e == "scroll down"]) - before, 2)

    def test_type_and_key_into_target(self):
        self.cu("type", "hello world", "--into", TITLE)
        self.cu("key", "Return", "--into", TITLE)
        self.wait_for(lambda e: e == "text hello world")

    def test_into_blocks_typing_into_other_windows(self):
        r = self.cu("type", "should not appear", "--into", "some-other-app", check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusing", r.stderr)
        self.cu("key", "Return", "--into", TITLE)
        texts = self.wait_for(lambda e: e.startswith("text"))
        self.assertNotIn("should not appear", texts[-1])

    def test_windows_lists_target(self):
        self.assertIn(TITLE, self.cu("windows").stdout)

    def test_zoom_is_full_resolution(self):
        r = self.cu("zoom", "100", "100", "200", "100", "--factor", "2")
        from PIL import Image
        with Image.open(r.stdout.splitlines()[0]) as img:
            self.assertEqual(img.size, (round(200 * self.scale) * 2, round(100 * self.scale) * 2))


if __name__ == "__main__":
    unittest.main()
