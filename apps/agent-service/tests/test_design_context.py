from pathlib import Path

from mia import design_context


def test_load_design_context_reads_root_design_md(monkeypatch) -> None:
    design_context.clear_design_context_cache()
    root_design = Path(__file__).resolve().parents[3] / "DESIGN.md"

    assert design_context.DESIGN_CONTEXT_PATH == root_design
    assert "Mia Opencode Operator Design System" in design_context.load_design_context()


def test_load_design_context_handles_missing_file(monkeypatch, tmp_path) -> None:
    original_path = design_context.DESIGN_CONTEXT_PATH
    monkeypatch.setattr(design_context, "DESIGN_CONTEXT_PATH", tmp_path / "missing.md")
    design_context.clear_design_context_cache()

    assert design_context.load_design_context() == "No DESIGN.md found."
    monkeypatch.setattr(design_context, "DESIGN_CONTEXT_PATH", original_path)
    design_context.clear_design_context_cache()
