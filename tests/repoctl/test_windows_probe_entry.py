"""W1入口の報告契約。Windows primitiveの実機証拠とは区別する。"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.windows_probe import __main__ as probe


class EntryTests(unittest.TestCase):
    def test_unsupported_platform_is_blocked_without_loading_native_suite(self):
        output = io.StringIO()
        with mock.patch.object(probe, "native_supported", return_value=False), \
                mock.patch("sys.argv", ["windows_probe"]), \
                mock.patch.object(probe.unittest.defaultTestLoader, "discover") as discover, \
                contextlib.redirect_stdout(output):
            self.assertEqual(3, probe.main())
        discover.assert_not_called()
        self.assertEqual("BLOCKED", json.loads(output.getvalue())["status"])

    def test_explicit_evidence_requires_new_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "evidence"
            with mock.patch("sys.argv", ["windows_probe", "--out", str(out)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                # Native tests are deliberately not loaded by this structural fixture.
                with mock.patch.object(probe, "native_supported", return_value=False):
                    self.assertEqual(3, probe.main())
                before = (out / "summary.json").read_bytes()
                with self.assertRaises(FileExistsError):
                    probe.main()
                self.assertEqual(before, (out / "summary.json").read_bytes())

    def test_discovery_exception_preserves_error_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "evidence"
            with mock.patch("sys.argv", ["windows_probe", "--out", str(out)]), \
                    mock.patch.object(probe, "native_supported", return_value=True), \
                    mock.patch.object(probe, "native_suite", side_effect=ImportError("fixture")), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(2, probe.main())
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual("ERROR", summary["status"])
            self.assertEqual("preflight", summary["evidence_class"])
            self.assertIn("ASKILLS-W1-EXECUTION", summary["reason"])

    def test_empty_and_skipped_suites_cannot_pass(self):
        class Skipped(unittest.TestCase):
            @unittest.skip("fixture unavailable")
            def test_skip(self):
                pass

        for suite in (unittest.TestSuite(), unittest.defaultTestLoader.loadTestsFromTestCase(Skipped)):
            with self.subTest(suite=suite), \
                    mock.patch("sys.argv", ["windows_probe"]), \
                    mock.patch.object(probe, "native_supported", return_value=True), \
                    mock.patch.object(probe, "native_suite", return_value=suite), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(1, probe.main())

    def test_failed_subtest_is_identifiable(self):
        class Failed(unittest.TestCase):
            def test_fixture(self):
                with self.subTest(boundary="collision"):
                    self.fail("fixture")

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Failed)
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=probe.Result).run(suite)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual("FAIL", result.cases[0]["status"])
        self.assertIn("collision", result.cases[0]["id"])

    def test_empty_mandatory_module_is_rejected(self):
        with mock.patch.object(Path, "is_file", return_value=True), \
                mock.patch.object(unittest.TestLoader, "discover", return_value=unittest.TestSuite()):
            with self.assertRaisesRegex(RuntimeError, "ASKILLS-W1-SUITE-EMPTY"):
                probe.native_suite()
