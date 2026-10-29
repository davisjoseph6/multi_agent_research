"""Apply one audited correction to the existing v2 synthetic protocol runtime.

Fails closed on unknown source versions. Never modifies unrelated files.
Run as `python -m scripts.step72_123_apply_v3` from benchmark root.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import os
import tempfile

ORIGINAL_SHA256 = "4112728f18358fe245ab82a7a486cf53bb206d10967112b9dc82e8b202fa3ac2"
OLD = '''                if s["stage"] in ("pretest", "practice"):
                    belief = Belief(s["mastery"].copy())
                    belief.observe(item.concept, correct)
                    s["mastery"] = belief.mastery
'''
NEW = '''                if s["stage"] == "pretest":
                    # Baseline assessment gives observation evidence, but
                    # must NOT apply the BKT *instructional learning* transition.
                    # This fixes an unearned .10 mastery increase in the
                    # provisional v2 runtime after every pre-test item.
                    s["mastery"][item.concept] = BKT().posterior(
                        s["mastery"][item.concept], correct)
                elif s["stage"] == "practice":
                    belief = Belief(s["mastery"].copy())
                    belief.observe(item.concept, correct)
                    s["mastery"] = belief.mastery
'''


def main():
    path = Path(__file__).resolve().parents[1] / "src/prototype/study_v2_runtime.py"
    source = path.read_text(encoding="utf-8")
    if source.count(NEW) == 1 and OLD not in source:
        print("BASELINE BKT CORRECTION ALREADY APPLIED")
        return
    actual = sha256(path.read_bytes()).hexdigest()
    if actual != ORIGINAL_SHA256 or source.count(OLD) != 1:
        raise SystemExit(
            "ABORT: the existing v2 runtime differs from the audited source. "
            "Do not overwrite it; inspect git diff and resolve changes manually.\n"
            f"Actual SHA256: {actual}")
    new_source = source.replace(OLD, NEW, 1)
    compile(new_source, str(path), "exec")
    handle, staging = tempfile.mkstemp(dir=path.parent, prefix=".step_v3_", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            f.write(new_source)
        os.chmod(staging, path.stat().st_mode & 0o777)
        os.replace(staging, path)
    finally:
        if os.path.exists(staging):
            os.unlink(staging)
    print("BASELINE BKT CORRECTION APPLIED; rerun full tests")


if __name__ == "__main__":
    main()
