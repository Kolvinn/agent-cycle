from __future__ import annotations

from pathlib import Path

import pytest

from langchain_claude_test.app.commands import CommandSet, parse
from langchain_claude_test.app.config import builtin_modes, load_modes
from langchain_claude_test.app.session import SessionStore

PKG = Path(__file__).resolve().parents[2] / "src" / "langchain_claude_test" / "app"


def test_parse_only_treats_a_leading_slash_as_a_command():
    assert parse("hello") is None
    assert parse("  /graph where is X validated?").name == "graph"
    assert parse("/graph where is X validated?").args == "where is X validated?"
    assert parse("/Help").name == "help"
    assert parse("//not a command") is None
    assert parse("/") is None


def test_command_set_knows_modes_builtins_and_passthrough(tmp_path: Path):
    modes = builtin_modes(PKG)
    cs = CommandSet(modes)
    assert cs.is_mode("graph") and cs.is_mode("chat")
    assert cs.is_builtin("resume") and not cs.is_mode("resume")
    assert cs.is_passthrough("compact")
    assert "/graph" in cs.suggestions() and "/fork" in cs.suggestions()
    assert "/graph" in cs.help_text()


def test_modes_file_adds_and_overrides(tmp_path: Path):
    f = tmp_path / "modes.toml"
    f.write_text(
        'default = "chat"\n\n[modes.reviewer]\nkind = "agent"\ndescription = "r"\n'
        'system_prompt = { preset = "claude_code", append = "review" }\ntools = ["Read"]\n\n'
        '[modes.chat]\ndescription = "mine"\n'
    )
    modes = load_modes(f, base_dir=PKG)
    assert modes.names() == ("chat", "graph", "reviewer")
    assert modes["reviewer"].tools == ("Read",)
    assert modes["reviewer"].sdk_system_prompt(PKG) == {"type": "preset", "preset": "claude_code", "append": "review"}
    assert modes["chat"].description == "mine"
    assert modes.graph.name == "graph"
    assert modes.graph.sdk_system_prompt(PKG)["type"] == "file"


def test_a_prompt_file_resolves_beside_the_modes_file_then_in_the_package(tmp_path: Path):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "mine.md").write_text("be terse")
    (tmp_path / "modes.toml").write_text(
        '[modes.terse]\nsystem_prompt = { file = "prompts/mine.md" }\n\n'
        '[modes.shared]\nsystem_prompt = { file = "prompts/graph_system.md" }\n'
    )
    modes = load_modes(tmp_path / "modes.toml", base_dir=PKG)
    # the working directory's own file wins
    assert modes["terse"].sdk_system_prompt(PKG)["path"] == str((tmp_path / "prompts" / "mine.md").resolve())
    # a name only the package has falls back to the package
    assert modes["shared"].sdk_system_prompt(PKG)["path"] == str((PKG / "prompts" / "graph_system.md").resolve())


def test_modes_file_rejects_unknown_keys(tmp_path: Path):
    f = tmp_path / "modes.toml"
    f.write_text('[modes.x]\nbogus = 1\n')
    with pytest.raises(ValueError, match="unknown key"):
        load_modes(f, base_dir=PKG)


def test_session_store_round_trips(tmp_path: Path):
    store = SessionStore(tmp_path / "sessions")
    a = store.create("alpha")
    assert store.exists("alpha") and store.names() == ["alpha"]
    a.focus = "graph"
    a.conversations["chat"] = "sess-1"
    store.save(a)
    b = store.load("alpha")
    assert b.focus == "graph" and b.conversations == {"chat": "sess-1"} and b.thread_id == "alpha"
    auto = store.create()
    assert auto.name.startswith("s-")
    with pytest.raises(FileExistsError):
        store.create("alpha")
    with pytest.raises(ValueError):
        store.create("bad name!")
    assert store.events_path("alpha") == tmp_path / "sessions" / "alpha" / "events.jsonl"
