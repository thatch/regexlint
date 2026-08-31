import os
import re
import subprocess
import sys
from io import StringIO
from types import SimpleNamespace

import pytest

from regexlint import cmdline


@pytest.fixture
def in_process_pool(monkeypatch):
    # Keep the checkers real while making resource/error assertions deterministic.
    monkeypatch.setattr(
        cmdline.multiprocessing, "Pool", lambda: SimpleNamespace(imap=map)
    )


@pytest.fixture
def opened_files(monkeypatch):
    files = []

    def track_open(*args, **kwargs):
        stream = open(*args, **kwargs)
        files.append(stream)
        return stream

    monkeypatch.setattr(cmdline, "open", track_open, raising=False)
    yield files
    # Keep failed closure assertions from leaking handles during regression runs.
    for stream in files:
        stream.close()


@pytest.fixture
def lexer_module(tmp_path, monkeypatch):
    module = tmp_path / "report_lexers.py"
    module.write_text(
        "from pygments.lexer import RegexLexer\n"
        "from pygments.token import Text\n"
        "\n"
        "class Clean(RegexLexer):\n"
        "    tokens = {'root': [('abc', Text)]}\n"
        "\n"
        "class Broken(RegexLexer):\n"
        "    tokens = {'root': [('else|elseif', Text)]}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    yield module.stem
    sys.modules.pop(module.stem, None)


@pytest.mark.parametrize(
    ("patterns", "expected"),
    [
        (["abc"], "'abc' OK\n"),
        (
            ["caf\u00e9", "xyz", "caf\u00e9"],
            "'caf\u00e9' OK\n'xyz' OK\n'caf\u00e9' OK\n",
        ),
    ],
)
def test_raw_report_text(
    tmp_path, in_process_pool, opened_files, capsys, patterns, expected
):
    report = tmp_path / "r\u00e9sum\u00e9 report.txt"
    report.write_text("stale report content that must be replaced", encoding="utf-8")

    assert cmdline.main(["--output_file", str(report), "--regex"] + patterns) is None

    assert len(opened_files) == 1
    assert opened_files[0].closed
    assert report.read_text(encoding="utf-8") == expected
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize("lexer", ["Clean", "Broken", "RegexLexer"])
def test_lexer_report_matches_stdout(
    tmp_path, in_process_pool, opened_files, lexer_module, capsys, lexer
):
    args = [lexer_module + ":" + lexer]
    if lexer == "Clean":
        args.insert(0, "--verbose")

    def run(extra_args):
        if lexer == "Broken":
            with pytest.raises(SystemExit) as exc:
                cmdline.main(extra_args + args)
            assert exc.value.code == 1
        else:
            assert cmdline.main(extra_args + args) is None

    run([])
    expected = capsys.readouterr()
    assert expected.err == ""
    if lexer == "Clean":
        assert expected.out == "Module report_lexers\nClean OK\n"
    elif lexer == "Broken":
        assert "E105: Potential out of order alternation" in expected.out
    else:
        assert expected.out == ""

    report = tmp_path / "report.txt"
    report.write_text("stale report", encoding="utf-8")
    run(["--output_file", str(report)])

    assert len(opened_files) == 1
    assert opened_files[0].closed
    assert report.read_text(encoding="utf-8") == expected.out
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_raw_findings_keep_normal_return(
    tmp_path, in_process_pool, opened_files, capsys
):
    args = ["--regex", "else|elseif"]
    assert cmdline.main(args) is None
    expected = capsys.readouterr().out
    assert "E105: Potential out of order alternation" in expected

    report = tmp_path / "report.txt"
    assert cmdline.main(["--output_file", str(report)] + args) is None

    assert opened_files[0].closed
    assert report.read_text(encoding="utf-8") == expected
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize(
    ("args", "error"),
    [
        (["--regex", "("], re.error),
        (["regexlint_missing_report_fixture"], ModuleNotFoundError),
    ],
)
def test_checking_error_closes_report(
    tmp_path, in_process_pool, opened_files, args, error
):
    with pytest.raises(error):
        cmdline.main(["--output_file", str(tmp_path / "report.txt")] + args)

    assert len(opened_files) == 1
    assert opened_files[0].closed


@pytest.mark.parametrize("invalid", [False, True])
def test_stdout_stays_open(monkeypatch, in_process_pool, invalid):
    output = StringIO()
    monkeypatch.setattr(sys, "stdout", output)

    if invalid:
        with pytest.raises(re.error):
            cmdline.main(["--regex", "("])
    else:
        assert cmdline.main(["--regex", "abc"]) is None
        assert output.getvalue() == "'abc' OK\n"

    assert not output.closed


def test_write_error_propagates_and_closes_report(monkeypatch, in_process_pool):
    error = OSError("report write failed")

    class FailingWriter(StringIO):
        def write(self, text):
            raise error

    output = FailingWriter()
    monkeypatch.setattr(cmdline, "open", lambda *args, **kwargs: output, raising=False)
    try:
        with pytest.raises(OSError) as exc:
            cmdline.main(["--output_file", "unused.txt", "--regex", "abc"])
        assert exc.value is error
        assert output.closed
    finally:
        output.close()


def test_report_open_error(tmp_path):
    report = tmp_path / "missing-parent" / "report.txt"
    with pytest.raises(FileNotFoundError):
        cmdline.main(["--output_file", str(report), "--regex", "abc"])
    assert not report.exists()


def test_missing_arguments_does_not_create_report(tmp_path, capsys):
    report = tmp_path / "report.txt"
    with pytest.raises(SystemExit) as exc:
        cmdline.main(["--output_file", str(report)])
    assert exc.value.code == 2
    assert "need some arguments" in capsys.readouterr().err
    assert not report.exists()


def test_raw_regex_output_file_subprocess(tmp_path):
    report = tmp_path / "report.txt"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "regexlint.cmdline",
            "--output_file",
            str(report),
            "--regex",
            "abc",
        ],
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == proc.stderr == ""
    assert report.read_text(encoding="utf-8") == "'abc' OK\n"


@pytest.mark.parametrize(("lexer", "exit_code"), [("Clean", 0), ("Broken", 1)])
def test_lexer_output_file_subprocess(tmp_path, lexer_module, lexer, exit_code):
    report = tmp_path / "report.txt"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "regexlint.cmdline",
            "--output_file",
            str(report),
            "--verbose",
            lexer_module + ":" + lexer,
        ],
        env=dict(os.environ, PYTHONPATH=str(tmp_path)),
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    assert proc.returncode == exit_code, proc.stderr
    assert proc.stdout == proc.stderr == ""
    output = report.read_text(encoding="utf-8")
    if lexer == "Clean":
        assert output == "Module report_lexers\nClean OK\n"
    else:
        assert output.startswith("Module report_lexers\n")
        assert "E105: Potential out of order alternation" in output
