import subprocess
import sys


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
