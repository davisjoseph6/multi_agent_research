"""No-network tests for Chromium user-local OS dependency selection.

Do not install host packages or launch any browser in this unit test.
"""
from pathlib import Path
import os
import subprocess


HELPER = Path(__file__).resolve().parents[1] / "ops/rct/qa_browser_userlibs.sh"


def test_wrapper_shell_syntax():
    result = subprocess.run(["bash", "-n", str(HELPER)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def _resolve(tmp_path, distro, library):
    fakebin = tmp_path / "bin"
    fakebin.mkdir(exist_ok=True)
    fake = fakebin / "apt-cache"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import os,sys\n"
        "name=sys.argv[-1]\n"
        "known={'libnspr4','libnss3'}\n"
        "if os.environ['FAKE_UBUNTU_VERSION']=='24.04':\n"
        " known|={'libasound2t64','libglib2.0-0t64','libatk1.0-0t64','libcups2t64'}\n"
        "elif os.environ['FAKE_UBUNTU_VERSION']=='22.04':\n"
        " known|={'libasound2','libglib2.0-0','libatk1.0-0','libcups2'}\n"
        "candidate='1.0-1' if name in known else '(none)'\n"
        "print(f'{name}:\\n  Installed: (none)\\n  Candidate: {candidate}')\n"
    )
    fake.chmod(0o755)
    env = dict(os.environ, FAKE_UBUNTU_VERSION=distro,
               PATH=str(fakebin) + os.pathsep + os.environ.get("PATH", ""))
    return subprocess.run(
        ["bash", str(HELPER), "--resolve-package", library],
        capture_output=True, text=True, env=env
    )


def test_ubuntu_noble_time64_resolves_concrete_runtime_packages(tmp_path):
    for library, package in (
        ("libasound.so.2", "libasound2t64"),
        ("libglib-2.0.so.0", "libglib2.0-0t64"),
        ("libatk-1.0.so.0", "libatk1.0-0t64"),
        ("libcups.so.2", "libcups2t64"),
        ("libnss3.so", "libnss3"),
        ("libnssutil3.so", "libnss3"),
    ):
        outcome = _resolve(tmp_path, "24.04", library)
        assert outcome.returncode == 0, (library, outcome.stderr)
        assert outcome.stdout.strip() == package


def test_ubuntu_jammy_falls_back_to_old_nonvirtual_packages(tmp_path):
    for library, package in (
        ("libasound.so.2", "libasound2"),
        ("libglib-2.0.so.0", "libglib2.0-0"),
        ("libatk-1.0.so.0", "libatk1.0-0"),
        ("libcups.so.2", "libcups2"),
    ):
        outcome = _resolve(tmp_path, "22.04", library)
        assert outcome.returncode == 0, (library, outcome.stderr)
        assert outcome.stdout.strip() == package


def test_unknown_or_unavailable_dependencies_fail_closed(tmp_path):
    unknown = _resolve(tmp_path, "24.04", "libunrecognized.so")
    assert unknown.returncode != 0
    assert "Unknown browser library" in unknown.stderr
    unavailable = _resolve(tmp_path, "24.04", "libgbm.so.1")
    assert unavailable.returncode != 0
    assert "No installable OS package" in unavailable.stderr
