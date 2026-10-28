"""Offline tests for Module 4 code (no API key needed). Run: uv run pytest tests/test_m04_offline.py"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LESSONS = REPO / "lessons"
LAB = REPO / "labs" / "lab2_phi-masking"


def load(path: Path, name: str):
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(path.parent))


def test_lab_solution_matches_the_toolkit():
    for name in ("classes", "detect", "mask", "vault", "minimize", "leakscan", "pa_tools"):
        assert (LAB / "solution/phi_guard" / f"{name}.py").read_text() == (REPO / "src/sentinel/privacy" / f"{name}.py").read_text(), name


def test_l03_leak_tour_finds_every_leak_point(capsys, tmp_path, monkeypatch):
    mod = load(LESSONS / "M04-L03_where-sensitive-data-leaks-in-an-agent/final/leak_tour.py", "m04_leak_tour")
    monkeypatch.setattr(mod, "OUT", tmp_path)
    mod.main()
    rows = [l for l in capsys.readouterr().out.splitlines() if l[:2] in ("1.", "2.", "3.", "4.", "5.", "6.", "+ ")]
    assert len(rows) == 7 and all(int(l[34:46]) > 0 for l in rows)


def test_l04_recall_climbs_by_stage(capsys):
    load(LESSONS / "M04-L04_detection-with-presidio-patterns-and/final/detect_demo.py", "m04_detect").main()
    out = capsys.readouterr().out
    assert "75.0%" in out and "92.9%" in out and "100.0%" in out


def test_l05_vault_grants_and_denies(capsys):
    load(LESSONS / "M04-L05_masking-strategies-redaction/final/masking_demo.py", "m04_masking").main()
    out = capsys.readouterr().out
    assert "GRANTED k.osei" in out and out.count("DENIED") == 2 and "ciphertext only: True" in out


def test_l06_only_both_boundaries_get_to_zero(capsys):
    load(LESSONS / "M04-L06_masking-at-the-tool-boundary-vs-the-log/final/boundaries_demo.py", "m04_bounds").main()
    rows = {l[:40].strip(): l[40:].split() for l in capsys.readouterr().out.splitlines() if l[:2] in ("A.", "B.", "C.")}
    a, b, c = (rows[k] for k in sorted(rows))
    assert int(a[0]) > 0 and int(a[1]) > 0
    assert int(b[0]) > 0 and 0 < int(b[1]) < int(a[1])          # log masking alone: model still sees PHI; names slip
    assert c == ["0", "0"]


def test_privacy_redactor_plugs_into_audit_hooks():
    from sentinel.privacy import PrivacyRedactor
    out = PrivacyRedactor("redact")({"note": "Call Maria Delgado at 617-555-0143", "ssn": "912-45-6789"})
    assert out["ssn"] == "[REDACTED]" and "617-555-0143" not in out["note"] and "[PERSON]" in out["note"]
