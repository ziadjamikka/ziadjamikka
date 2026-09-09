#!/usr/bin/env python3
"""
Tic-Tac-Toe vs. a Minimax AI — playable straight from the GitHub profile README.

How it works
------------
1. A visitor clicks an empty cell in the README. The link opens a pre-filled
   GitHub issue whose title is  ttt|move|<cell>  (cell = 0..8).
2. The workflow in .github/workflows/tictactoe.yml runs this script.
3. The script applies the visitor's move (X), lets the AI answer (O),
   rewrites the board between the <!-- TTT:START --> / <!-- TTT:END -->
   markers in README.md, updates game/state.json and writes game/comment.md
   (the reply the workflow posts on the issue before closing it).

Run locally to (re)render the board without playing:
    python game/tictactoe.py --init
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
STATE = ROOT / "game" / "state.json"
COMMENT = ROOT / "game" / "comment.md"

HUMAN, AI, EMPTY = "X", "O", "-"
AI_MISTAKE_RATE = 0.12          # chance the AI plays a random legal move (keeps it beatable)
MAX_RECENT = 6
MAX_HALL_OF_FAME = 10
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
START = "<!-- TTT:START -->"
END = "<!-- TTT:END -->"


# ---------------------------------------------------------------- state
def default_state() -> dict:
    return {
        "board": EMPTY * 9,
        "stats": {"games": 0, "human_wins": 0, "ai_wins": 0, "draws": 0},
        "recent": [],
        "hall_of_fame": [],
        "last_result": None,
    }


def load_state() -> dict:
    if STATE.exists():
        data = json.loads(STATE.read_text(encoding="utf-8"))
        base = default_state()
        base.update(data)
        return base
    return default_state()


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- rules
def winner(b: str) -> str | None:
    for x, y, z in LINES:
        if b[x] != EMPTY and b[x] == b[y] == b[z]:
            return b[x]
    return None


def winning_line(b: str) -> tuple | None:
    for line in LINES:
        x, y, z = line
        if b[x] != EMPTY and b[x] == b[y] == b[z]:
            return line
    return None


def full(b: str) -> bool:
    return EMPTY not in b


def place(b: str, i: int, p: str) -> str:
    return b[:i] + p + b[i + 1:]


# ---------------------------------------------------------------- minimax
def minimax(b: str, player: str) -> int:
    """Score from the AI's point of view: +1 AI win, -1 human win, 0 draw."""
    w = winner(b)
    if w == AI:
        return 1
    if w == HUMAN:
        return -1
    if full(b):
        return 0
    scores = [minimax(place(b, i, player), HUMAN if player == AI else AI)
              for i in range(9) if b[i] == EMPTY]
    return max(scores) if player == AI else min(scores)


def ai_move(b: str) -> int:
    empties = [i for i in range(9) if b[i] == EMPTY]
    if random.random() < AI_MISTAKE_RATE:
        return random.choice(empties)
    scored = [(minimax(place(b, i, AI), HUMAN), i) for i in empties]
    best = max(s for s, _ in scored)
    return random.choice([i for s, i in scored if s == best])


# ---------------------------------------------------------------- rendering
def issue_url(repo: str, cell: int) -> str:
    return (f"https://github.com/{repo}/issues/new?title=ttt%7Cmove%7C{cell}"
            "&body=Just+click+%22Submit+new+issue%22+%E2%80%94+no+need+to+edit+anything.+%F0%9F%8E%AE")


def reset_url(repo: str) -> str:
    return (f"https://github.com/{repo}/issues/new?title=ttt%7Cnew"
            "&body=Just+click+%22Submit+new+issue%22+to+start+a+fresh+game.")


def board_html(b: str, repo: str) -> str:
    rows = []
    for r in range(3):
        cells = []
        for c in range(3):
            i = r * 3 + c
            if b[i] == HUMAN:
                cells.append('<td align="center"><img src="assets/ttt/x.svg" width="88" alt="X"/></td>')
            elif b[i] == AI:
                cells.append('<td align="center"><img src="assets/ttt/o.svg" width="88" alt="O"/></td>')
            else:
                cells.append(f'<td align="center"><a href="{issue_url(repo, i)}">'
                             f'<img src="assets/ttt/empty.svg" width="88" alt="Play cell {i + 1}"/></a></td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return '<table align="center">\n' + "\n".join(rows) + "\n</table>"


def badge(label: str, value, color: str) -> str:
    label = label.replace(" ", "%20").replace("-", "--")
    return (f'<img src="https://img.shields.io/badge/{label}-{value}-{color}'
            f'?style=for-the-badge&labelColor=0c1622" alt="{label}: {value}"/>')


def user_link(u: str) -> str:
    return f'<a href="https://github.com/{u}"><b>@{u}</b></a>'


def render_section(state: dict, repo: str) -> str:
    s = state["stats"]
    b = state["board"]
    turn_line = ("It's your move — you are <b>X</b>, the AI is <b>O</b>. "
                 "Click any empty cell to play. Anyone can join the current game!")
    if state.get("last_result"):
        turn_line = state["last_result"] + "<br/>" + turn_line

    hall = ", ".join(user_link(e["user"]) for e in state["hall_of_fame"][:MAX_HALL_OF_FAME]) or "nobody yet — be the first!"
    recent = ", ".join(user_link(u) for u in state["recent"][:MAX_RECENT]) or "nobody yet"

    parts = [
        START,
        '<p align="center">' + turn_line + "</p>",
        "",
        board_html(b, repo),
        "",
        '<p align="center">',
        badge("Games", s["games"], "23444b"),
        badge("Humans won", s["human_wins"], "628d7c"),
        badge("AI won", s["ai_wins"], "000000"),
        badge("Draws", s["draws"], "1f2b29"),
        "</p>",
        "",
        f'<p align="center">🏆 <b>Beat the AI:</b> {hall}<br/>'
        f'🎮 <b>Recent players:</b> {recent}<br/>'
        f'<sub>Stuck or want a clean board? <a href="{reset_url(repo)}">Start a new game</a> · '
        f'Moves take ~30 seconds to show up (a GitHub Action plays the AI\'s turn).</sub></p>',
        END,
    ]
    return "\n".join(parts)


def update_readme(section: str) -> None:
    text = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit("README.md is missing the TTT markers.")
    README.write_text(pattern.sub(lambda _: section, text), encoding="utf-8")


def ascii_board(b: str) -> str:
    sym = {HUMAN: "X", AI: "O", EMPTY: "·"}
    rows = [" ".join(sym[b[r * 3 + c]] for c in range(3)) for r in range(3)]
    return "```\n" + "\n".join(rows) + "\n```"


# ---------------------------------------------------------------- game flow
def finish_game(state: dict, user: str, result: str) -> str:
    """Record the outcome, reset the board, and return a human-readable line."""
    s = state["stats"]
    s["games"] += 1
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if result == HUMAN:
        s["human_wins"] += 1
        state["hall_of_fame"].insert(0, {"user": user, "date": today})
        state["hall_of_fame"] = state["hall_of_fame"][:MAX_HALL_OF_FAME]
        line = f"🎉 <b>{user_link(user)} beat the AI!</b> A fresh board is ready below."
    elif result == AI:
        s["ai_wins"] += 1
        line = f"🤖 The AI won the last game (final move by {user_link(user)}). Revenge? Fresh board below."
    else:
        s["draws"] += 1
        line = f"🤝 Last game ended in a draw (final move by {user_link(user)}). Fresh board below."
    state["board"] = EMPTY * 9
    state["last_result"] = line
    return line


def touch_recent(state: dict, user: str) -> None:
    state["recent"] = [user] + [u for u in state["recent"] if u != user]
    state["recent"] = state["recent"][:MAX_RECENT]


def play(state: dict, title: str, user: str, repo: str) -> str:
    """Apply an issue to the state. Returns the comment to post on the issue."""
    profile = f"https://github.com/{repo.split('/')[0]}"
    m = re.fullmatch(r"ttt\|(move|new)(?:\|(\d))?", title.strip())
    if not m:
        return ("I couldn't read that move. Please click a cell on my profile instead of "
                "editing the issue title. 🙂")

    if m.group(1) == "new":
        if state["board"] == EMPTY * 9:
            return "The board is already empty — head back and make the first move! 🎮"
        state["board"] = EMPTY * 9
        state["last_result"] = f"🧹 {user_link(user)} reset the board."
        touch_recent(state, user)
        return f"Board reset. Back to [my profile]({profile}) for a fresh game!"

    cell = int(m.group(2))
    b = state["board"]
    if b[cell] != EMPTY:
        return (f"Cell {cell + 1} is already taken — the board probably changed since you loaded it. "
                f"Refresh [my profile]({profile}) and pick another one.")

    touch_recent(state, user)
    b = place(b, cell, HUMAN)
    state["board"] = b
    state["last_result"] = None
    lines = [f"### 🎮 Move accepted", f"You played **X** in cell **{cell + 1}**."]

    w = winner(b)
    if w == HUMAN:
        finish_game(state, user, HUMAN)
        lines.append("**You beat the AI!** 🎉 Your name is now on my profile's Hall of Fame.")
    elif full(b):
        finish_game(state, user, "draw")
        lines.append("It's a **draw** 🤝 — the AI doesn't lose easily.")
    else:
        ai = ai_move(b)
        b = place(b, ai, AI)
        state["board"] = b
        lines.append(f"The AI answered with **O** in cell **{ai + 1}**.")
        w = winner(b)
        if w == AI:
            finish_game(state, user, AI)
            lines.append("**The AI wins this one.** 🤖 A fresh board is waiting for your revenge.")
        elif full(b):
            finish_game(state, user, "draw")
            lines.append("It's a **draw** 🤝 — well played.")

    lines.append(ascii_board(b))   # final position, even if the board was just reset
    lines.append(f"Head back to [my profile]({profile}) to keep playing — the board updates in a few seconds.")
    return "\n\n".join(lines)


def main() -> None:
    repo = os.environ.get("REPO", "ziadjamikka/ziadjamikka")
    state = load_state()

    if "--init" in sys.argv:
        update_readme(render_section(state, repo))
        save_state(state)
        print("Board rendered.")
        return

    title = os.environ.get("ISSUE_TITLE", "")
    user = os.environ.get("ISSUE_AUTHOR", "someone")
    comment = play(state, title, user, repo)
    update_readme(render_section(state, repo))
    save_state(state)
    COMMENT.write_text(comment + "\n", encoding="utf-8")
    try:
        print(comment)
    except BrokenPipeError:
        pass


if __name__ == "__main__":
    main()
