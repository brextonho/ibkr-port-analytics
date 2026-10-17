"""The CLI behaves the same whichever folder you run it from."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from portfolio import cli


@pytest.fixture(autouse=True)
def no_real_env(monkeypatch):
    # main() moves to the project folder, where your real .env lives; don't load it
    monkeypatch.setattr("portfolio.config.load_dotenv", lambda *a, **k: None)


def test_runs_from_the_project_folder_but_keeps_your_paths(tmp_path, monkeypatch):
    calls = {}

    def fake_run(settings, *, xml_paths=(), benchmark=True, benchmark_holding=None):
        calls.update(cwd=os.getcwd(), xml=list(xml_paths), db=settings.database_url)
        return 0

    monkeypatch.setattr("portfolio.ingest.run", fake_run)
    (tmp_path / "sub").mkdir()
    monkeypatch.chdir(tmp_path / "sub")  # somewhere outside the project

    assert cli.main(["ingest", "--xml", "a.xml", "../b.xml", "--db", "mine.db", "--no-benchmark"]) == 0
    assert Path(calls["cwd"]) == cli.ROOT
    assert calls["xml"] == [str(tmp_path / "sub" / "a.xml"), str(tmp_path / "b.xml")]
    assert calls["db"] == f"sqlite:///{tmp_path / 'sub' / 'mine.db'}"


def test_default_database_is_in_the_project_folder(tmp_path, monkeypatch):
    calls = {}
    monkeypatch.setattr("portfolio.ingest.run", lambda settings, **kw: calls.update(db=settings.database_url) or 0)
    monkeypatch.chdir(tmp_path)
    cli.main(["ingest", "--no-benchmark"])
    # a relative path, now resolved from the project folder rather than tmp_path
    assert calls["db"] == "sqlite:///portfolio.db" and Path.cwd() == cli.ROOT
