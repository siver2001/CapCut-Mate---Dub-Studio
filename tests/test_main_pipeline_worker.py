import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import main as app_main


class PipelineWorkerBoundaryTests(unittest.TestCase):
    def test_pipeline_exception_becomes_structured_error_not_unhandled(self):
        old_excepthook = sys.excepthook
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with (
                patch.object(sys, "argv", ["main.py", "pipeline"]),
                patch(
                    "tools.dub_studio_pipeline.main",
                    side_effect=RuntimeError("quality gate test"),
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
                self.assertRaises(SystemExit) as raised,
            ):
                app_main.main()
        finally:
            sys.excepthook = old_excepthook

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("ERROR::", stdout.getvalue())
        self.assertIn("quality gate test", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
