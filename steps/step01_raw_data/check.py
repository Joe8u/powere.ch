from pathlib import Path

step_dir = Path(__file__).resolve().parent
repo_root = step_dir.parents[2]
lp_link = step_dir / "lastprofile"
sv_link = step_dir / "survey"

def check_link(link_path: Path, expect_tail: str) -> Path:
    assert link_path.is_symlink(), f"{link_path} ist kein Symlink"
    target = link_path.resolve()
    assert target.is_dir(), f"Ziel {target} existiert nicht"
    assert str(target).endswith(expect_tail), f"{link_path} zeigt auf {target}, erwartet …/{expect_tail}"
    assert any(target.rglob("*.*")), f"{target} scheint leer zu sein"
    return target

lp_tgt = check_link(lp_link, "data/lastprofile/raw")
sv_tgt = check_link(sv_link, "data/survey/raw")

print("✅ Step 1 OK — raw-data Symlinks zeigen auf existierende, nicht-leere Ordner.")
