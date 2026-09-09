#!/usr/bin/env python3
"""
One-time setup: fills in your GitHub username and links, then renders the
empty game board with the right issue links.

    python configure.py
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
README = ROOT / "README.md"


def ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def main() -> None:
    text = README.read_text(encoding="utf-8")

    username = ask("GitHub username (the repo must be named exactly the same)")
    if not re.fullmatch(r"[A-Za-z0-9-]+", username):
        sys.exit("That doesn't look like a GitHub username.")
    linkedin = ask("LinkedIn profile URL", "https://www.linkedin.com/in/")
    portfolio = ask("Portfolio URL (leave empty to remove the Portfolio badges)")

    text = text.replace("YOUR_USERNAME", username)
    text = text.replace("YOUR_LINKEDIN_URL", linkedin)
    if portfolio:
        text = text.replace("YOUR_PORTFOLIO_URL", portfolio)
    else:
        text = re.sub(r'<a href="YOUR_PORTFOLIO_URL">.*?</a>\n?', "", text)

    README.write_text(text, encoding="utf-8")

    env = dict(os.environ, REPO=f"{username}/{username}")
    subprocess.run([sys.executable, str(ROOT / "game" / "tictactoe.py"), "--init"], check=True, env=env)
    print(f"\nDone. Push this folder to https://github.com/{username}/{username} and you're live.")


if __name__ == "__main__":
    main()
