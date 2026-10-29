"""Run a fresh disposable, loopback-only SYNTHETIC browser.

`python -m scripts.step123_v3_local_browser` from benchmark directory.
Do NOT paste the printed credential into chats or public logs.
"""
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory

from src.prototype.study_v3_demo_api import create_synthetic_browser_app


def main():
    with TemporaryDirectory(prefix="ijcai_v3_BROWSER_SYNTHETIC_") as folder:
        token = secrets.token_urlsafe(32)
        app = create_synthetic_browser_app(Path(folder)/"v3_synthetic.sqlite3",token=token)
        print("\nSYNTHETIC DEVELOPMENT ONLY. NOT AN APPROVED HUMAN STUDY.")
        print("Open: http://127.0.0.1:5062/trial-v3")
        print("Private local development token (do not share):",token)
        print("Test using only fictional SYN_ participant IDs.")
        print("When finished, Ctrl+C deletes the disposable database.\n")
        app.run(host="127.0.0.1",port=5062,debug=False,use_reloader=False)


if __name__ == "__main__":
    main()
