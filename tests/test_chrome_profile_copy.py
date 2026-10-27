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


if __name__ == "__main__":
    unittest.main()
