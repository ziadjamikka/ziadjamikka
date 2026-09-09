# Setup guide

Everything in this folder goes into your **profile repository** — the special
public repo whose name is exactly your GitHub username
(`github.com/<username>/<username>`). GitHub shows its README on your profile.

## 1. Create the profile repo

1. On GitHub click **New repository**.
2. Name it **exactly** your username, keep it **Public**, don't add any files.
3. Make sure **Issues** are enabled (Settings → General → Features). The game
   needs them.

## 2. Fill in your details

```bash
python configure.py
```

It asks for your GitHub username, LinkedIn URL and portfolio URL, replaces
every placeholder in `README.md`, and renders the empty game board with the
correct links.

(If you prefer doing it by hand: find-and-replace `YOUR_USERNAME`,
`YOUR_LINKEDIN_URL` and `YOUR_PORTFOLIO_URL` in `README.md`, then run
`REPO=<username>/<username> python game/tictactoe.py --init`.)

## 3. Push

```bash
git init
git add .
git commit -m "✨ Profile README"
git branch -M main
git remote add origin https://github.com/<username>/<username>.git
git push -u origin main
```

Open your profile — the banner, the 3D shapes and the board are already live.

## 4. Enable the automations

1. Go to **Settings → Actions → General → Workflow permissions** and choose
   **Read and write permissions**, then save.
2. Open the **Actions** tab. If GitHub asks you to enable workflows, click
   **Enable**.
3. Run the **🐍 Contribution snake** workflow once by hand
   (Actions → 🐍 Contribution snake → Run workflow). It creates the `output`
   branch that the snake images in the README point to. After that it runs
   daily on its own.
4. The **📊 Profile stats** workflow renders the stats, languages and streak
   cards into the `stats` branch. It runs automatically on the first push and
   then daily; run it by hand the same way if you ever want a refresh.

## 5. Test the game

Click any empty cell on your profile, then press **Submit new issue**.
Within ~30 seconds the Action plays the AI's move, rewrites the board,
comments on the issue and closes it. You'll see the commit
`🎮 @you played (#1)` in the repo.

## Customising

| Want to change… | Where |
|---|---|
| Palette, speed, size of the drawings | `tools/generate_svgs.py` (palette at the top of the file), then run it |
| Swap the avatar illustration | replace `assets/avatar_source.png`, run the generator |
| Banner avatar in original colours instead of tinted | set `AVATAR_DUOTONE = False` in `tools/generate_svgs.py` (or point the README at `assets/banner_original_colors.svg`) |
| How often the AI blunders (default 12%) | `AI_MISTAKE_RATE` in `game/tictactoe.py` |
| Wording of the game section / issue replies | `render_section()` and `play()` in `game/tictactoe.py` |
| Stats cards (palette, layout, which numbers) | `tools/generate_stats.py`, then run it (`python tools/generate_stats.py dist`) |
| Typing intro lines | the `lines=` param in the readme-typing-svg URL (use `+` for spaces, `;` between lines) |

## Files

```
README.md                      the profile page
configure.py                   one-time placeholder replacement
assets/banner.svg              hero: name + avatar wired into an animated neural network
assets/avatar_source.png       your illustration — the generator builds the banner avatar from it
assets/avatar.png              circular crop, original colours (use it as your GitHub profile picture)
assets/avatar_duotone.png      the same crop tinted to the palette
assets/banner_original_colors.svg  banner variant with the illustration in its original colours
assets/neural_net.svg          animated neural network (About section)
assets/neural_net_deep.svg     animated deep neural network (Tech stack section)
assets/glasses.svg             PATHIRA VISION swinging wireframe glasses (Projects section)
assets/ttt/{empty,x,o}.svg     game cells
game/tictactoe.py              minimax engine + README renderer
game/state.json                current board and stats (edited by the Action)
tools/generate_svgs.py         regenerates every SVG above
tools/generate_stats.py        renders the stats / languages / streak cards (published to the `stats` branch)
.github/workflows/tictactoe.yml  plays the AI's turn when an issue is opened
.github/workflows/snake.yml      daily contribution-snake animation
.github/workflows/stats.yml      daily stats cards
```

All animations are pure SVG (SMIL) — GitHub strips JavaScript from READMEs,
so this is the only way to get motion and it works in every browser that
GitHub supports.

## Notes

- Your phone number from the CV was left out on purpose; a public GitHub
  profile is scraped constantly. Add it only if you really want it there.
- Pin your best repos (PATHIRA VISION, the video generator, the kitchen
  monitor…) from the profile page — the README gets people interested, pinned
  repos let them dig in.
- The stats, languages and streak cards are rendered inside this repo by the
  📊 Profile stats workflow, so they don't depend on the public
  `github-readme-stats` / `streak-stats` servers (which are often paused or
  rate-limited). The typing intro, `capsule-render` footer and `komarev`
  view counter are still free community services; if one is ever down the
  image simply won't load, nothing else breaks.
