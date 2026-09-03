import os
import re
import subprocess
import sys
from unittest.mock import Mock

import pytest

from regexlint import cmdline


@pytest.fixture
def serial_main(monkeypatch):
    monkeypatch.setattr(
        cmdline.multiprocessing,
        "Pool",
        Mock(side_effect=AssertionError("Serial mode must not create a process pool")),
    )
    return cmdline.main


@pytest.fixture
def lexer_module(tmp_path, monkeypatch):
    name = "serial_cli_fixture"
    (tmp_path / (name + ".py")).write_text(
        """\
from pygments.lexer import RegexLexer
from pygments.token import Text

class Clean(RegexLexer):
    tokens = {"root": [("abc", Text)]}

class Other(RegexLexer):
    tokens = {"root": [("def", Text)]}

class Broken(RegexLexer):
    tokens = {"root": [("else|elseif", Text)]}
""",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    yield name
    sys.modules.pop(name, None)


def test_serial_regex(capsys, serial_main):
    assert serial_main(["--no_parallel", "--regex", "abc"]) is None
    assert capsys.readouterr().out == "'abc' OK\n"


def test_serial_regex_order_and_duplicates(capsys, serial_main):
    assert serial_main(["--no_parallel", "--regex", "beta", "alpha", "beta"]) is None
    assert capsys.readouterr().out == "'beta' OK\n'alpha' OK\n'beta' OK\n"


def test_serial_regex_diagnostic(capsys, serial_main):
    # Raw-regex mode reports findings without changing the exit status.
    assert serial_main(["--no_parallel", "--regex", "a|ab"]) is None
    output = capsys.readouterr().out
    assert "E105: Potential out of order alternation between 'a' and 'ab'" in output
    assert "'a|ab'" in output
    assert "OK" not in output


def test_serial_invalid_regex(serial_main):
    with pytest.raises(re.error, match="unterminated"):
        serial_main(["--no_parallel", "--regex", "("])


def test_serial_missing_module(serial_main):
    with pytest.raises(ImportError, match="regexlint_missing_serial_test_module"):
        serial_main(["--no_parallel", "regexlint_missing_serial_test_module"])


@pytest.mark.parametrize(
    "args,message",
    [([], "need some arguments"), (["--unknown"], "no such option")],
)
def test_serial_argument_errors(args, message, capsys, serial_main):
    with pytest.raises(SystemExit) as exc:
        serial_main(["--no_parallel"] + args)
    assert exc.value.code == 2
    assert message in capsys.readouterr().err


def test_serial_clean_lexer(lexer_module, capsys, serial_main):
    assert serial_main(["--no_parallel", lexer_module + ":Clean"]) is None
    assert capsys.readouterr().out == ""


def test_serial_lexer_diagnostic(lexer_module, capsys, serial_main):
    with pytest.raises(SystemExit) as exc:
        serial_main(["--no_parallel", lexer_module + ":Broken"])
    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "(Broken:root:pat#1) E105:" in output
    assert "Potential out of order alternation between 'else' and 'elseif'" in output


def test_serial_lexer_module(lexer_module, capsys, serial_main):
    with pytest.raises(SystemExit) as exc:
        serial_main(["--no_parallel", "--verbose", lexer_module])
    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert output.startswith("Module %s\nClean OK\nOther OK\n" % lexer_module)
    assert "(Broken:root:pat#1) E105:" in output


def test_serial_lexer_order_and_duplicates(lexer_module, capsys, serial_main):
    args = [lexer_module + ":" + name for name in ["Clean", "Other", "Clean"]]
    assert serial_main(["--no_parallel", "--verbose"] + args) is None
    assert capsys.readouterr().out == "".join(
        "Module %s\n%s OK\n" % (lexer_module, name)
        for name in ["Clean", "Other", "Clean"]
    )


def test_serial_empty_lexer_collection(lexer_module, capsys, serial_main):
    # The imported base class has no token rules to check.
    assert serial_main(["--no_parallel", lexer_module + ":RegexLexer"]) is None
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("raw_regex", [True, False])
def test_parallel_mapping(raw_regex, lexer_module, capsys, monkeypatch):
    pool = Mock()
    pool.imap.side_effect = map
    factory = Mock(return_value=pool)
    monkeypatch.setattr(cmdline.multiprocessing, "Pool", factory)
    args = ["--regex", "abc"] if raw_regex else ["--verbose", lexer_module + ":Clean"]
    assert cmdline.main(args) is None
    expected = "'abc' OK\n" if raw_regex else "Module %s\nClean OK\n" % lexer_module
    assert capsys.readouterr().out == expected
    factory.assert_called_once_with()
    pool.imap.assert_called_once()


@pytest.mark.parametrize(
    "target,code,output",
    [
        ("regex", 0, "'abc' OK\n"),
        ("Clean", 0, ""),
        ("Broken", 1, "(Broken:root:pat#1) E105:"),
    ],
)
def test_serial_command(target, code, output, lexer_module, tmp_path):
    args = ["--regex", "abc"] if target == "regex" else [lexer_module + ":" + target]
    proc = subprocess.run(
        [sys.executable, "-m", "regexlint.cmdline", "--no_parallel"] + args,
        env=dict(os.environ, PYTHONPATH=str(tmp_path)),
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == code, proc.stderr
    assert proc.stderr == ""
    if target == "Broken":
        assert output in proc.stdout
    else:
        assert proc.stdout == output
