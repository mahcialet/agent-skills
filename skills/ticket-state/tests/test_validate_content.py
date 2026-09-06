from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


class ContentValidatorTests(unittest.TestCase):
    def test_distribution_content_is_valid(self) -> None:
        skill_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(skill_root / "scripts" / "validate_content.py")],
            cwd=Path.cwd(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
