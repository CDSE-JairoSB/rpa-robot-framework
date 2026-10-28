import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from libraries.DataProcessor import DataProcessor


class CopyChromeUserDataTests(unittest.TestCase):
    def setUp(self):
        self.processor = DataProcessor()
        self.temp = tempfile.mkdtemp(prefix="chrome_copy_test_")
        self.source_root = os.path.join(self.temp, "Chrome")
        self.profile = os.path.join(self.source_root, "Default")
        os.makedirs(self.profile)
        with open(os.path.join(self.source_root, "Local State"), "w", encoding="utf-8") as handle:
            handle.write("{}")
        with open(os.path.join(self.profile, "Preferences"), "w", encoding="utf-8") as handle:
            handle.write("{}")

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_copies_profile_when_local_state_is_blocked(self):
        destination = os.path.join(self.temp, "dest")

        original_copy2 = shutil.copy2

        def copy2_side_effect(src, dst, *args, **kwargs):
            if src.endswith("Local State"):
                raise PermissionError(1, "Operation not permitted", src)
            return original_copy2(src, dst, *args, **kwargs)

        with patch("shutil.copy2", side_effect=copy2_side_effect):
            self.processor.copy_chrome_user_data(self.profile, "Default", destination)

        self.assertFalse(os.path.exists(os.path.join(destination, "Local State")))
        self.assertTrue(os.path.exists(os.path.join(destination, "Default", "Preferences")))

    def test_raises_when_profile_directory_is_blocked(self):
        destination = os.path.join(self.temp, "dest")
        with patch("shutil.copytree", side_effect=PermissionError(1, "Operation not permitted")):
            with self.assertRaises(PermissionError) as raised:
                self.processor.copy_chrome_user_data(self.profile, "Default", destination)
        self.assertIn("seed_chrome_profile.sh", str(raised.exception))

    def test_resolve_chrome_binary_with_cli_override(self):
        fake_binary = os.path.join(self.temp, "fake_chrome")
        with open(fake_binary, "w") as f:
            f.write("#!/bin/sh\n")
        resolved = self.processor.resolve_chrome_binary_path(cli_override=fake_binary)
        self.assertEqual(resolved, fake_binary)

    def test_resolve_chrome_binary_with_env_var(self):
        fake_binary = os.path.join(self.temp, "env_chrome")
        with open(fake_binary, "w") as f:
            f.write("#!/bin/sh\n")
        with patch.dict(os.environ, {"CHROME_BINARY_PATH": fake_binary}):
            resolved = self.processor.resolve_chrome_binary_path()
            self.assertEqual(resolved, fake_binary)

    def test_resolve_chrome_binary_with_shutil_which(self):
        with patch("shutil.which", side_effect=lambda name: "/usr/bin/" + name if name == "google-chrome" else None):
            with patch("os.path.exists", return_value=False):
                resolved = self.processor.resolve_chrome_binary_path()
                self.assertEqual(resolved, "/usr/bin/google-chrome")

    def test_resolve_chrome_binary_fallback_on_linux(self):
        with patch("shutil.which", return_value=None):
            with patch("os.path.exists", return_value=False):
                with patch("sys.platform", "linux"):
                    resolved = self.processor.resolve_chrome_binary_path()
                    self.assertEqual(resolved, "google-chrome")

    def test_default_chrome_profile_path_linux(self):
        linux_profile = os.path.join(self.temp, ".config", "google-chrome", "Default")
        os.makedirs(linux_profile, exist_ok=True)
        with patch("libraries.DataProcessor.DataProcessor._is_readable_dir") as mock_readable:
            def readable_side_effect(path):
                return path == linux_profile
            mock_readable.side_effect = readable_side_effect
            with patch("os.path.expanduser", return_value=self.temp):
                resolved = self.processor.default_chrome_profile_path("Default")
                self.assertEqual(resolved, linux_profile)


if __name__ == "__main__":
    unittest.main()
