"""Exercise the browser formatter without a browser or model calls."""
from pathlib import Path
import shutil
import subprocess
import unittest


class AnswerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is needed for formatter tests')
    def test_answer_formatting(self):
        subprocess.run(['node', str(Path(__file__).with_name('test_answer.cjs'))], check=True, capture_output=True)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is needed for view tests')
    def test_discussion_view(self):
        subprocess.run(['node', str(Path(__file__).with_name('test_discussion.cjs'))], check=True, capture_output=True)
