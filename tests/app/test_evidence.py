"""The fenced executor behind attach_finding: what it refuses, what it runs, what it keeps."""

from __future__ import annotations

from pathlib import Path

import pytest

from langchain_claude_test.app.harness import evidence


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("\n".join(f"line {i}" for i in range(1, 201)) + "\n")
    (tmp_path / "secret").write_text("nope\n")
    return tmp_path


@pytest.mark.parametrize(
    "command, reason",
    [
        ("cat src/app.py | rm -rf /", "one command only"),
        ("cat src/app.py; ls", "one command only"),
        ("cat $(ls)", "one command only"),
        ("rm -rf src", "not an allowed command"),
        ("python script.py", "not an allowed command"),
        ("git push origin main", "git is read-only"),
        ("git checkout -- .", "git is read-only"),
        ("sed -i 's/a/b/' src/app.py", "sed may only print"),
        ("sed 's/a/b/' src/app.py", "sed may only print"),
        ("find . -name '*.py' -delete", "find may not execute"),
        ("find . -exec rm {} +", "find may not execute"),
        ("cat /etc/passwd", "outside the working directory"),
        ("cat ../../etc/passwd", "outside the working directory"),
        ("cat 'unterminated", "could not parse"),
        ("", "empty command"),
    ],
)
def test_refusals(repo: Path, command: str, reason: str):
    result = evidence.plan(command, repo)
    assert isinstance(result, str) and result.startswith("REFUSED") and reason in result


def test_allowed_commands_are_planned_with_their_class(repo: Path):
    assert evidence.plan("sed -n '10,20p' src/app.py", repo) == evidence.Plan(("sed", "-n", "10,20p", "src/app.py"), "read")
    assert evidence.plan("grep -n 'line 7' src/app.py", repo).klass == "survey"
    assert evidence.plan("git log --oneline -3", repo).klass == "read"
    assert evidence.plan("/bin/cat src/app.py", repo).argv[0] == "cat"


def test_execution_keeps_the_output_and_caps_it(repo: Path):
    out = evidence.run_command("sed -n '10,12p' src/app.py", repo)
    assert isinstance(out, evidence.Output) and out.text == "line 10\nline 11\nline 12" and not out.truncated
    out = evidence.run_command("cat src/app.py", repo)
    assert out.truncated and out.text.endswith("… 120 more lines not kept") and out.text.count("\n") == evidence.MAX_LINES
    out = evidence.run_command("grep -c line src/app.py", repo)
    assert out.text == "200"
    out = evidence.run_command("cat missing.py", repo)
    assert out.returncode != 0 and "missing.py" in out.text  # stderr comes back when stdout is empty
    assert evidence.run_command("rm src/app.py", repo).startswith("REFUSED") and (repo / "src" / "app.py").exists()
