"""The committed demo XML is exactly what scripts/make_demo_xml.py produces;
the script asserts the books tie on every day while it writes them."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def test_demo_xml_matches_its_generator(fixture_xml_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "make_demo_xml.py"
    spec = importlib.util.spec_from_file_location("make_demo_xml", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up while loading
    spec.loader.exec_module(module)
    assert module.simulate() == fixture_xml_path.read_text(), "rerun: uv run python scripts/make_demo_xml.py"
