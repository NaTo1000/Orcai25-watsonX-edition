import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orcai_security import DEFAULT_CONFIG_PATH, OrcaiSecurityStack, main


class CommandLineTests(unittest.TestCase):
    def test_health_command_succeeds(self):
        self.assertEqual(main(["health"]), 0)

    def test_default_config_path_is_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("pathlib.Path.cwd", return_value=Path(directory)):
                stack = OrcaiSecurityStack()
        self.assertEqual(stack.config["system"]["environment"], "production")
        self.assertTrue(DEFAULT_CONFIG_PATH.is_absolute())


if __name__ == "__main__":
    unittest.main()
