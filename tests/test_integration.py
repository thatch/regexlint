import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

STRIP_PATH_RE = re.compile(r"^.*[\\/](?=demo_integration\.py)", re.M)


class IntegrationTest(unittest.TestCase):
    def test_readme_example_one(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "demo_integration.py").write_text(
                """\
from pygments.lexer import RegexLexer, bygroups
from pygments.token import Text

class T(RegexLexer):
    tokens = {
        "root": [
            ("(else|elseif)", Text),
        ],
    }
"""
            )

            env = dict(os.environ, PYTHONPATH=d)
            proc = subprocess.run(
                [sys.executable, "-m", "regexlint.cmdline", "demo_integration"],
                env=env,
                encoding="utf-8",
                stdout=subprocess.PIPE,
            )
            output = STRIP_PATH_RE.sub("", proc.stdout)

            self.assertEqual(
                """\
demo_integration.py:7: (T:root:pat#1) E105: Potential out of order alternation between 'else' and 'elseif'
              ("(else|elseif)", Text),
                      ^ here
""",
                output,
            )

    def test_readme_example_two(self):
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "demo_integration.py").write_text(
                """\
from pygments.lexer import RegexLexer, bygroups
from pygments.token import Text

class T(RegexLexer):
    tokens = {
        "root": [
            ("(foo)\\s+(bar)", bygroups(Text, Text)),
        ],
    }
"""
            )

            env = dict(os.environ, PYTHONPATH=d)
            proc = subprocess.run(
                [sys.executable, "-m", "regexlint.cmdline", "demo_integration"],
                env=env,
                encoding="utf-8",
                stdout=subprocess.PIPE,
            )
            output = STRIP_PATH_RE.sub("", proc.stdout)

            self.assertEqual(
                """\
demo_integration.py:7: (T:root:pat#1) E108: Gap in capture groups using bygroups
              ("(foo)\\s+(bar)", bygroups(Text, Text)),
                     ^ here
""",
                output,
            )
