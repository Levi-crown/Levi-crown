"""Generate the terminal-themed SVG assets for the Levi-crown profile README.

usage: python tools/build_assets.py assets   (also updates image links in README.md)
"""
import datetime as dt
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

# GitHub dark background, GitHub "dimmed" ANSI palette for terminal colors
BG, BAR, LINE = "#0d1117", "#161b22", "#30363d"
TXT, DIM, HI = "#adbac7", "#768390", "#cdd9e5"
RED, GRN, YEL, BLU, MAG, CYN = "#e5534b", "#57ab5a", "#daaa3f", "#539bf5", "#b083f0", "#39c5cf"
W = 840
FONT = "'JetBrains Mono','Fira Code','Cascadia Mono',Consolas,'DejaVu Sans Mono',Menlo,monospace"

BASE_CSS = f"""
text{{font-family:{FONT};white-space:pre}}
.t{{fill:{TXT}}} .d{{fill:{DIM}}} .h{{fill:{HI}}} .b{{font-weight:700}}
.r{{fill:{RED}}} .g{{fill:{GRN}}} .y{{fill:{YEL}}} .bl{{fill:{BLU}}} .m{{fill:{MAG}}} .c{{fill:{CYN}}}
.a{{opacity:0}}
@keyframes in{{to{{opacity:1}}}}
@keyframes vis{{0%,100%{{opacity:1}}}}
@media (prefers-reduced-motion:reduce){{
  *{{animation:none!important}} .a{{opacity:1!important}} .draw{{stroke-dashoffset:0!important}} .cv,.cur,.game,.ping{{display:none}} .roll{{transform:none!important}}
}}
"""


def cw(fs):
    return fs * 0.6


def text(x, y, parts, fs=14, cls="", style=""):
    """parts: str or list of (string, class). textLength pins monospace width across fonts."""
    if isinstance(parts, str):
        parts = [(parts, "t")]
    full = "".join(p for p, _ in parts).rstrip()
    n = len(full)
    if n == 0:
        return ""
    spans = "".join(f'<tspan class="{c}">{escape(p)}</tspan>' for p, c in parts)
    st = f' style="{style}"' if style else ""
    return (f'<text x="{x}" y="{y}" font-size="{fs}" textLength="{n * cw(fs):.1f}" '
            f'lengthAdjust="spacing" xml:space="preserve" class="{cls}"{st}>{spans}</text>')


def appear(t, dur=0.15):
    return f"animation:in {dur}s linear {t:.2f}s forwards"


TITLE = "levi@kali: ~"
BAR_H = 34
TOP = BAR_H + 30  # baseline of the first prompt line


def frame(h, title=TITLE):
    """A terminal window: macOS-style traffic lights on the left, a red (root) terminal icon beside the centered title."""
    out = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="6" fill="{BG}" stroke="{LINE}"/>',
           f'<path d="M0.5 {BAR_H}V6.5a6 6 0 0 1 6-6h{W - 13}a6 6 0 0 1 6 6V{BAR_H}z" fill="{BAR}"/>',
           f'<line x1="0.5" y1="{BAR_H}" x2="{W - 0.5}" y2="{BAR_H}" stroke="{LINE}"/>']
    cy = BAR_H / 2
    # close / minimize / zoom in the standard macOS colors
    out += [f'<circle cx="{20 + i * 20}" cy="{cy}" r="6" fill="{c}"/>' for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"])]
    tl = len(title) * cw(12)
    tx = W / 2 - (tl + 26) / 2  # icon + gap + title, centered as one unit
    out.append(f'<g transform="translate({tx - 14.5:.1f} 0)"><rect x="14.5" y="10.5" width="18" height="14" rx="2.5" fill="none" stroke="{RED}" stroke-width="1.3"/>'
               f'<path d="M18.5 14.5l3 2.5-3 2.5M23 20.5h5" fill="none" stroke="{RED}" stroke-width="1.3" '
               f'stroke-linecap="round" stroke-linejoin="round"/></g>')
    out.append(text(tx + 26, 21.5, [(title, "d")], fs=12))
    return out


def svg(h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
            f'role="img" aria-label="{escape(label)}"><title>{escape(label)}</title>'
            f'<style>{BASE_CSS}</style>' + "".join(body) + "</svg>")


# the classic bash prompt: bold green user@host, bold blue path
PROMPT = [("levi@kali", "g b"), (":", "t"), ("~", "bl b"), ("$", "t")]
PROMPT_LEN = len("".join(p for p, _ in PROMPT)) + 1  # the space before the command


def prompt(x, y, t, cmd=None, type_start=None, type_dur=None, kid=""):
    """One prompt line. Optionally types `cmd` (list of parts) with a stepping cover + cursor."""
    out = [text(x, y, PROMPT, cls="a", style=appear(t, 0.01))]
    if cmd:
        cx = x + PROMPT_LEN * cw(14)
        n = len("".join(p for p, _ in cmd))
        dist = n * cw(14)
        out.append(text(cx, y, cmd))
        out.append(f"<style>@keyframes ty{kid}{{to{{transform:translateX({dist:.1f}px)}}}}</style>")
        mv = f"animation:ty{kid} {type_dur}s steps({n}) {type_start}s forwards"
        out.append(f'<rect class="cv" x="{cx - 1}" y="{y - 15}" width="{dist + 4:.1f}" height="20" fill="{BG}" style="{mv}"/>')
        out.append(f'<g style="{mv}"><rect class="cur" x="{cx}" y="{y - 12}" width="{cw(14):.1f}" height="16" '
                   f'fill="{TXT}" opacity="0" style="animation:vis {type_dur + 0.2}s linear {type_start}s"/></g>')
    return out


# GitHub's mark (Octicons, MIT), 16x16
OCTOCAT = ("M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94"
           "-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07"
           "-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27"
           ".68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95"
           ".29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z")


def mascot():
    """Tux in a GitHub tee, the Apple logo in one flipper, the Android robot in the other, the Kali dragon behind.
    Drawn in a 250 x 240 box; the dragon's head bobs, Tux blinks and both logos float."""
    blue, deep, body, edge, ink, green, silver = "#367bf0", "#1f56c4", "#30363d", "#545d68", "#1b1f24", "#3ddc84", "#d0d7de"
    css = ("@keyframes bob{50%{transform:rotate(-4deg)}}@keyframes wink{0%,90%,100%{transform:scaleY(1)}94%{transform:scaleY(.1)}}"
           "@keyframes hop{50%{transform:translateY(-4px)}}"
           ".bob{transform-box:fill-box;transform-origin:10% 100%;animation:bob 3.2s ease-in-out infinite}"
           ".wink{transform-box:fill-box;transform-origin:center;animation:wink 4s infinite}"
           ".hop{animation:hop 1.6s ease-in-out infinite}.hop2{animation:hop 1.6s ease-in-out .8s infinite}")
    dragon = (f'<path d="M104 112C78 86 46 64 16 30c12 30 12 40 22 50-12 0-18 8-20 18 18-4 28 4 30 12-10 2-14 8-14 16 22-8 44-6 70 6z" fill="{deep}"/>'
              f'<path d="M150 212c40 10 76 2 84-20 4-12-4-20-12-14" fill="none" stroke="{blue}" stroke-width="10" stroke-linecap="round"/>'
              f'<path d="M224 176l-12-8 2 14z" fill="{blue}"/>'
              f'<g class="bob"><path d="M140 140C196 124 214 92 198 52" fill="none" stroke="{blue}" stroke-width="20" stroke-linecap="round"/>'
              f'<path d="M206 62l14-4-8 12zM210 86h14l-10 10zM200 108l12 6-14 4z" fill="{deep}"/>'
              f'<path d="M214 42c-6-16-28-20-46-12l-22 8c-5 2-4 9 2 9l22 1c8 7 26 12 40 6z" fill="{blue}"/>'
              f'<path d="M198 30l22-22-8 26zM208 36l28-12-20 20z" fill="{deep}"/>'
              f'<path d="M150 45l20 1" stroke="{deep}" stroke-width="2"/><circle cx="186" cy="36" r="3" fill="{RED}"/></g>')
    tux = (f'<ellipse cx="76" cy="150" rx="13" ry="32" transform="rotate(28 76 150)" fill="{body}" stroke="{edge}" stroke-width="1.5"/>'
           f'<ellipse cx="164" cy="150" rx="13" ry="32" transform="rotate(-28 164 150)" fill="{body}" stroke="{edge}" stroke-width="1.5"/>'
           f'<ellipse cx="120" cy="94" rx="36" ry="34" fill="{body}" stroke="{edge}" stroke-width="1.5"/>'
           f'<ellipse cx="120" cy="150" rx="50" ry="66" fill="{body}" stroke="{edge}" stroke-width="1.5"/>'
           f'<ellipse cx="120" cy="94" rx="34.5" ry="32.5" fill="{body}"/>'
           f'<path d="M96 98c0-16 10-24 24-24s24 8 24 24c0 12-10 20-24 20s-24-8-24-20z" fill="{HI}"/>'
           f'<g class="wink"><ellipse cx="110" cy="92" rx="6.5" ry="8.5" fill="#fff" stroke="{ink}" stroke-width="1.2"/>'
           f'<ellipse cx="130" cy="92" rx="6.5" ry="8.5" fill="#fff" stroke="{ink}" stroke-width="1.2"/>'
           f'<ellipse cx="111.5" cy="94" rx="3" ry="4" fill="{ink}"/><ellipse cx="128.5" cy="94" rx="3" ry="4" fill="{ink}"/></g>'
           f'<path d="M82 124c24-8 52-8 76 0l6 62c-24 22-64 22-88 0z" fill="{BAR}" stroke="{LINE}" stroke-width="1.5"/>'
           f'<path transform="translate(104 142) scale(2)" d="{OCTOCAT}" fill="{HI}"/>'
           f'<path d="M104 106c8-6 24-6 32 0-4 8-12 12-16 12s-12-4-16-12z" fill="{YEL}"/>'
           f'<path d="M106 107c8 3 20 3 28 0" fill="none" stroke="#b7862b" stroke-width="1.2"/>'
           f'<ellipse cx="98" cy="214" rx="22" ry="9" fill="{YEL}"/><ellipse cx="142" cy="214" rx="22" ry="9" fill="{YEL}"/>')
    apple = (f'<mask id="bite"><rect width="250" height="240" fill="#fff"/><circle cx="84" cy="168" r="9" fill="#000"/></mask>'
             f'<g class="hop"><path mask="url(#bite)" d="M56 160c-7-8-22-7-25 8-3 16 8 32 18 32 3 0 4-2 7-2s4 2 7 2c10 0 20-14 22-26-2-14-17-21-29-14z" fill="{silver}"/>'
             f'<path d="M57 154c-1-10 5-16 13-18 0 9-6 16-13 18z" fill="{silver}"/></g>')
    android = (f'<g class="hop2" fill="{green}"><path d="M170 160a18 18 0 0 1 36 0z"/>'
               f'<path d="M178 144l-5-8M198 144l5-8" stroke="{green}" stroke-width="2.5" stroke-linecap="round"/>'
               f'<circle cx="180" cy="152" r="2.2" fill="{BG}"/><circle cx="196" cy="152" r="2.2" fill="{BG}"/>'
               f'<rect x="170" y="163" width="36" height="28" rx="4"/><rect x="162" y="164" width="6" height="20" rx="3"/>'
               f'<rect x="208" y="164" width="6" height="20" rx="3"/><rect x="178" y="188" width="6" height="12" rx="3"/>'
               f'<rect x="192" y="188" width="6" height="12" rx="3"/></g>')
    # flipper tips drawn over the logos so Tux grips them
    grip = "".join(f'<ellipse cx="{x}" cy="176" rx="9" ry="7" fill="{body}" stroke="{edge}" stroke-width="1.5"/>' for x in (76, 164))
    return f"<style>{css}</style>{dragon}{tux}{apple}{android}{grip}"


# ---------------------------------------------------------------- neofetch
def neofetch():
    rows = [
        ("Role", "AI-native full-stack developer"),
        ("OS", "Kali Linux, Windows"),
        ("Android", "Android apps, AOSP, Magisk"),
        ("IoT", "ESP32, Arduino, Raspberry Pi"),
        ("Security", "Burp Suite, Metasploit, Nmap"),
        ("AI", "Claude Code, Antigravity, Cursor"),
        ("Certs", "Cisco Ethical Hacker, Endpoint Security"),
        ("Level", "always learning"),
    ]
    y0 = TOP + 34 + 44  # output starts under the prompt; header and rule take two lines
    h = y0 + len(rows) * 24 + 40
    b = frame(h)
    b += prompt(24, TOP, 0.1, [("neofetch", "g")], 0.3, 0.5, "n")
    # centered on the output block, from the user@host line down to the color bar
    ay = y0 + (len(rows) * 24 - 48) / 2 - 120
    b.append(f'<g class="a" transform="translate(22 {ay:.1f})" style="{appear(0.95, 0.3)}">{mascot()}</g>')
    ix, vx = 300, 300 + 12 * cw(14)
    st = appear(0.95, 0.01)
    b.append(text(ix, y0 - 44, [("levi", "bl b"), ("@", "t"), ("kali", "bl b")], cls="a", style=st))
    b.append(text(ix, y0 - 24, [("-" * 9, "d")], cls="a", style=st))
    for i, (k, v) in enumerate(rows):
        y = y0 + i * 24
        st = appear(1.0 + i * 0.05, 0.01)
        b.append(text(ix, y, [(k + ":", "bl b")], cls="a", style=st))
        b.append(text(vx, y, v, cls="a", style=st))
    ansi = ["#2d333b", RED, GRN, YEL, BLU, MAG, CYN, TXT]
    for i, c in enumerate(ansi):
        b.append(f'<rect class="a" x="{ix + i * 30}" y="{y0 + len(rows) * 24 - 6}" width="30" height="16" fill="{c}" style="{appear(1.0 + len(rows) * 0.05, 0.01)}"/>')
    return svg(h, b, "neofetch: " + ". ".join(f"{k} {v}" for k, v in rows) + ".")


# 16 x 16 glyphs for the stats tiles
ICONS = {
    "grid": "".join(f'<rect x="{x}" y="{y}" width="7" height="7" rx="1.5" fill="{c}"/>'
                    for x, y, c in [(0, 0, "#006d32"), (9, 0, "#39d353"), (0, 9, "#26a641"), (9, 9, "#0e4429")]),
    "flame": '<path d="M8 0c1 4 5 5 5 10a5 5 0 0 1-10 0c0-3 2-4 2-6 1 1 2 2 2 4 1-2 1-5 1-8z" fill="#f0883e"/>',
    "bolt": f'<path d="M9 0 2 9h5l-1 7 7-9H8l1-7z" fill="{CYN}"/>',
    "star": f'<path d="M8 .5l2.2 4.8 5.3.6-3.9 3.6 1.1 5.2L8 12.1l-4.7 2.6 1.1-5.2L.5 5.9l5.3-.6z" fill="{YEL}"/>',
    "repo": f'<rect x="2" y="1" width="12" height="14" rx="1.5" fill="none" stroke="{TXT}" stroke-width="1.5"/><path d="M5 1v14" stroke="{TXT}" stroke-width="1.5"/>',
    "people": f'<circle cx="8" cy="5" r="3.2" fill="{BLU}"/><path d="M1.5 15.5c0-3.6 2.9-5.8 6.5-5.8s6.5 2.2 6.5 5.8z" fill="{BLU}"/>',
}


# ---------------------------------------------------------------- stats
USER = "Levi-crown"
CAL = "contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}"


def graphql(query):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        try:
            token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
        except OSError:
            pass
    if not token:
        return None
    req = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": query}).encode(),
                                 {"Authorization": f"bearer {token}", "User-Agent": USER})
    return json.load(urllib.request.urlopen(req))["data"]["user"]


def stats():
    """Contribution stats drawn in-house; the third-party stats cards kept going down."""
    user = graphql(f'{{user(login:"{USER}"){{createdAt}}}}')
    if user is None:
        return None
    first = int(user["createdAt"][:4])
    now = dt.datetime.now(dt.timezone.utc)
    # contributionsCollection spans at most one year, so ask for each calendar year
    years = " ".join(f'y{y}:contributionsCollection(from:"{y}-01-01T00:00:00Z",to:"{min(now.year, y)}-12-31T23:59:59Z"){{{CAL}}}'
                     for y in range(first, now.year + 1))
    user = graphql(f'{{user(login:"{USER}"){{createdAt {years} last:contributionsCollection{{totalCommitContributions totalPullRequestContributions totalIssueContributions {CAL}}} '
                   f'followers{{totalCount}} repositories(ownerAffiliations:OWNER,privacy:PUBLIC,first:100){{totalCount nodes{{stargazerCount}}}}}}}}')
    days = sorted({d["date"]: d["contributionCount"]
                   for y in range(first, now.year + 1)
                   for w in user[f"y{y}"]["contributionCalendar"]["weeks"] for d in w["contributionDays"]}.items())
    days = [(dt.date.fromisoformat(d), n) for d, n in days if d <= now.date().isoformat()]
    total = sum(n for _, n in days)
    best, run = (0, None, None), 0
    for i, (d, n) in enumerate(days):
        run = run + 1 if n else 0
        if run > best[0]:
            best = (run, days[i - run + 1][0], d)
    # today doesn't break the streak until it's over
    cur, i = 0, len(days) - 1 - (days and days[-1][1] == 0)
    while i >= 0 and days[i][1]:
        cur, i = cur + 1, i - 1
    repos = user["repositories"]
    stars = sum(r["stargazerCount"] for r in repos["nodes"])
    since = dt.date.fromisoformat(user["createdAt"][:10])

    def day(d):
        return f"{d:%b} {d.day}"

    def plural(n, word):
        return f"{n:,} {word}{'' if n == 1 else 's'}"

    coll = user["last"]
    # six tiles: icon, odometer number, one-word label
    tiles = [("grid", f"{total:,}", "contributions"), ("flame", f"{cur:,}", "day streak"),
             ("bolt", f"{best[0]:,}", "best streak"), ("star", f"{stars:,}", "stars"),
             ("repo", f"{repos['totalCount']:,}", "repos"), ("people", f"{user['followers']['totalCount']:,}", "followers")]
    # contributions per calendar month, the last 12 months
    months = [((now.year * 12 + now.month - 1 - k) // 12, (now.month - 1 - k) % 12 + 1) for k in range(11, -1, -1)]
    per = dict.fromkeys(months, 0)
    for d, n in days:
        if (d.year, d.month) in per:
            per[d.year, d.month] += n
    series = [per[m] for m in months]

    weeks = coll["contributionCalendar"]["weeks"]
    gap = 3
    step = (W - 48 + gap) / len(weeks)  # heatmap spans the full text width
    cell = round(step - gap, 1)
    start = TOP + 34
    tw, th, ty0 = (W - 48 - 5 * 10) / 6, 64, start - 16
    py0, ph = ty0 + th + 34, 96  # plot top and height
    py1 = py0 + ph
    top = py1 + 44  # heatmap top, under the month labels
    h = round(top + 7 * step + 42)
    b = frame(h)
    b += prompt(24, TOP, 0.1, [("gh", "g"), (f" stats {USER}", "t")], 0.3, 0.6, "g")
    lh, nfs = 28, 22  # odometer line height, number size
    rolls = []
    for i, (ic, num, label) in enumerate(tiles):
        x, t = 24 + i * (tw + 10), 0.9 + i * 0.1
        b.append(f'<g class="a" style="{appear(t, 0.2)}"><rect x="{x:.1f}" y="{ty0}" width="{tw:.1f}" height="{th}" rx="6" fill="{BAR}" stroke="{LINE}"/>'
                 f'<g transform="translate({x + 12:.1f} {ty0 + 11})">{ICONS[ic]}</g>'
                 + text(x + 34, ty0 + 24, [(label, "d")], fs=11)
                 + f'<clipPath id="tc{i}"><rect x="{x:.1f}" y="{ty0 + 34}" width="{tw:.1f}" height="{lh}"/></clipPath><g clip-path="url(#tc{i})">')
        base = ty0 + 34 + lh - 7
        for j, ch in enumerate(num):
            cx = x + 12 + j * cw(nfs)
            if not ch.isdigit():
                b.append(text(cx, base, [(ch, "h b")], fs=nfs))
                continue
            # odometer: the column rolls up through a full cycle and lands on the digit (its resting place)
            d = int(ch)
            spans = "".join(f'<tspan x="{cx:.1f}" y="{base - (10 + d - k) * lh}">{k % 10}</tspan>' for k in range(11 + d))
            rolls.append(d)
            b.append(f'<text class="h b roll" font-size="{nfs}" style="animation:r{d} 1.4s cubic-bezier(.2,.7,.2,1) {t + 0.15 + j * 0.06:.2f}s both">{spans}</text>')
        b.append("</g></g>")
    b.append("<style>" + "".join(f"@keyframes r{d}{{from{{transform:translateY({(10 + d) * lh}px)}}}}" for d in sorted(set(rolls))) + "</style>")

    # ---- monthly contributions: gridlines, then the line draws itself, then area and dots
    tg = 1.6
    top_v = max(series) or 1
    mag = 10 ** math.floor(math.log10(top_v))
    ymax = next(f * mag for f in (1, 2, 2.5, 5, 10) if f * mag >= top_v)
    px0, px1 = 36, W - 36
    xs = [px0 + i * (px1 - px0) / (len(series) - 1) for i in range(len(series))]
    ys = [py1 - v / ymax * ph for v in series]
    gst = appear(tg, 0.2)
    for f in (0, 0.5, 1):
        gy = py1 - f * ph
        b.append(f'<line class="a" x1="{px0}" y1="{gy:.1f}" x2="{px1}" y2="{gy:.1f}" stroke="{LINE}" stroke-dasharray="2 4" style="{gst}"/>')
    for i, (yy, mm) in enumerate(months):
        lab = dt.date(yy, mm, 1).strftime("%b")
        b.append(text(xs[i] - len(lab) * cw(11) / 2, py1 + 20, [(lab, "d")], fs=11, cls="a", style=gst))
    pts = " ".join(f"{x:.1f} {y:.1f}" for x, y in zip(xs, ys))
    b.append(f'<path class="a" d="M{xs[0]:.1f} {py1:.1f}L{pts}L{xs[-1]:.1f} {py1:.1f}Z" fill="#39d353" fill-opacity=".12" '
             f'style="{appear(tg + 1.0, 0.5)}"/>')
    b.append(f'<path class="draw" d="M{pts}" pathLength="1" fill="none" stroke="#39d353" stroke-width="2" stroke-linejoin="round" '
             f'stroke-linecap="round" stroke-dasharray="1" stroke-dashoffset="1" style="animation:draw 1.2s ease-out {tg + 0.2:.2f}s forwards"/>')
    for i, (x, y) in enumerate(zip(xs, ys)):
        b.append(f'<circle class="a" cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#39d353" stroke="{BG}" stroke-width="2" '
                 f'style="{appear(tg + 0.2 + 1.2 * i / (len(xs) - 1), 0.1)}"/>')
    # latest month keeps pinging: it is still being written
    b.append(f'<circle class="ping" cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="4" fill="none" stroke="#39d353" stroke-width="2" '
             f'style="transform-box:fill-box;transform-origin:center;animation:ping 1.6s ease-out {tg + 1.5:.2f}s infinite;opacity:0"/>')
    # direct labels only on the peak and the current month
    for i in sorted({series.index(max(series)), len(series) - 1}):
        lab = f"{series[i]:,}"
        b.append(text(xs[i] - len(lab) * cw(11) / 2, ys[i] - 10, [(lab, "h b")], fs=11, cls="a", style=appear(tg + 1.4, 0.2)))
    b.append("<style>@keyframes draw{to{stroke-dashoffset:0}}"
             "@keyframes ping{0%{transform:scale(1);opacity:.8}100%{transform:scale(3);opacity:0}}</style>")
    # GitHub's dark-mode contribution greens
    levels = ["#2d333b", "#0e4429", "#006d32", "#26a641", "#39d353"]
    peak = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=0) or 1

    def shade(n):
        return levels[0] if n == 0 else levels[min(4, 1 + 4 * (n - 1) // peak)]

    x0 = 24
    t0 = tg + 1.4  # the heatmap fills in once the graph has drawn
    # chomper game: a muncher crawls the active weeks eating contribution cells while two viruses chase it;
    # the four busiest days are power pellets that leave the viruses crashed for a moment
    first = next((wi for wi, w in enumerate(weeks) if any(d["contributionCount"] for d in w["contributionDays"])), 0)
    path = [(wi, r if (wi - first) % 2 == 0 else 6 - r) for wi in range(first, len(weeks)) for r in range(7)]
    tick = min(0.15, max(0.05, 16 / len(path)))  # seconds per cell; keeps one round near 16 s
    loop, start, last = len(path) * tick, t0 + 1.2, max(1, len(path) - 1)
    at = {pos: n for n, pos in enumerate(path)}
    css, power = [], []
    busiest = sorted(((d["contributionCount"], w_i, d["date"]) for w_i, w in enumerate(weeks) for d in w["contributionDays"]
                      if d["contributionCount"] and w_i >= first), reverse=True)
    pellets = {date for _, _, date in busiest[:4]}

    def xy(wi, r):
        return x0 + wi * step, top + r * step

    for wi, w in enumerate(weeks):
        base, food = [], []
        for d in w["contributionDays"]:
            # the first week can start mid-week; place days by weekday
            r = (dt.date.fromisoformat(d["date"]).weekday() + 1) % 7
            x, y = xy(wi, r)
            rect = f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="2" fill="{{}}"{{}}/>'
            base.append(rect.format(levels[0], ""))
            n = d["contributionCount"]
            if n and (wi, r) in at:
                p = at[wi, r] * 100 / last  # share of the round when the muncher reaches this cell
                css.append(f"@keyframes e{len(css)}{{{p:.2f}%,100%{{opacity:0}}}}")
                food.append(rect.format(shade(n), f' style="animation:e{len(css) - 1} {loop:.2f}s step-end {start:.2f}s infinite"'))
                if d["date"] in pellets:
                    power.append(p)
            elif n:
                food.append(rect.format(shade(n), ""))
        b.append(f'<g class="a" style="{appear(t0 + wi * 0.012, 0.05)}">{"".join(base + food)}</g>')

    # power pellets: viruses stay crashed for 2.5 s after each one is eaten
    scare, span = [], 2.5 / loop * 100
    for p in power:
        if scare and p <= scare[-1][1]:
            scare[-1][1] = p + span
        else:
            scare.append([p, p + span])
    css.append("@keyframes scare{" + "".join(f"{a:.2f}%{{opacity:1}}{min(z, 100):.2f}%{{opacity:0}}" for a, z in scare) + "}")
    route = "M" + "L".join(f"{x + cell / 2:.1f} {y + cell / 2:.1f}" for x, y in (xy(*pos) for pos in path))
    css.append(f'@keyframes crawl{{from{{offset-distance:0%}}to{{offset-distance:100%}}}}@keyframes jaw{{50%{{opacity:0}}}}'
               f'.mv{{offset-path:path("{route}");offset-rotate:0deg}}.mv.head{{offset-rotate:auto}}.ko{{opacity:0}}')
    h2 = (cell + 1) / 2
    octagon = f'M{-h2 / 2:.1f} {-h2:.1f}H{h2 / 2:.1f}L{h2:.1f} {-h2 / 2:.1f}V{h2 / 2:.1f}L{h2 / 2:.1f} {h2:.1f}H{-h2 / 2:.1f}L{-h2:.1f} {h2 / 2:.1f}V{-h2 / 2:.1f}Z'

    def mover(lag, sprite, cls="mv"):
        t = start + lag * tick
        return (f'<g class="a" style="{appear(t, 0.05)}"><g class="{cls}" style="animation:crawl {loop:.2f}s linear {t:.2f}s infinite both">'
                f'{sprite}</g></g>')

    b.append(f'<style>{"".join(css)}</style><g class="game">')
    for lag, color in [(14, MAG), (8, RED)]:
        eyes = "".join(f'<rect x="{ex - 1.6:.1f}" y="-2.6" width="3.2" height="3.2" fill="{HI}"/><rect x="{ex - 0.4:.1f}" y="-1.6" width="1.4" height="1.6" fill="{BG}"/>'
                       for ex in (-2.4, 2.4))
        crashed = "".join(f'<path d="M{ex - 1.4:.1f} -2.4l2.8 2.8m0-2.8l-2.8 2.8" stroke="{HI}" stroke-width="1.1"/>' for ex in (-2.4, 2.4))
        b.append(mover(lag, f'<path d="{octagon}" fill="{color}"/>{eyes}'
                            f'<g class="ko" style="animation:scare {loop:.2f}s step-end {start:.2f}s infinite">'
                            f'<path d="{octagon}" fill="{DIM}"/>{crashed}</g>'))
    # the muncher faces right; offset-rotate turns it toward wherever it is heading
    b.append(mover(0, f'<path d="M{-h2:.1f} {-h2:.1f}H{h2:.1f}V{-h2 / 3:.1f}L0 0L{h2:.1f} {h2 / 3:.1f}V{h2:.1f}H{-h2:.1f}Z" fill="{CYN}"/>'
                      f'<rect x="{-h2:.1f}" y="{-h2:.1f}" width="{2 * h2:.1f}" height="{2 * h2:.1f}" rx="2" fill="{CYN}" '
                      f'style="animation:jaw {tick * 4:.2f}s step-end infinite"/>'
                      f'<rect x="-1.5" y="{-h2 + 2:.1f}" width="2.5" height="2.5" fill="{BG}"/>', "mv head"))
    b.append("</g>")
    ly = round(top + 7 * step + 16)
    cell, gap = 11, 3  # legend swatches stay small
    lx = W - 24 - len(levels) * (cell + gap) - 4 - 4 * cw(12)
    b.append(text(lx - 5 * cw(12), ly + 9, [("less", "d")], fs=12))
    for i, c in enumerate(levels):
        b.append(f'<rect x="{lx + i * (cell + gap)}" y="{ly}" width="{cell}" height="{cell}" rx="2" fill="{c}"/>')
    b.append(text(lx + len(levels) * (cell + gap) + 4, ly + 9, [("more", "d")], fs=12))
    return svg(h, b, f"GitHub stats. {total:,} contributions since {since:%B %Y}. Current streak {plural(cur, 'day')}, "
                     f"longest streak {plural(best[0], 'day')}. {repos['totalCount']} public repos, {plural(stars, 'star')}, "
                     f"{plural(user['followers']['totalCount'], 'follower')}. {coll['totalCommitContributions']:,} commits, "
                     f"{coll['totalPullRequestContributions']:,} pull requests and {coll['totalIssueContributions']:,} issues in the last year. "
                     "Contributions per month: " + ", ".join(f"{dt.date(y, m, 1):%b} {v:,}" for (y, m), v in zip(months, series)) + ".")


README = Path(__file__).parent.parent / "README.md"
readme = README.read_text(encoding="utf-8")
for name, fn in [("neofetch", neofetch), ("stats", stats)]:
    content = fn()
    if content is None:
        print("skipped", name, "(no GitHub token)")
        continue
    # GitHub's /raw/ redirect drops query strings and raw files are cached for 5 min,
    # so the content hash goes in the filename to give every version a fresh URL
    ver = hashlib.sha1(content.encode()).hexdigest()[:8]
    for old in OUT.glob(f"{name}*.svg"):
        old.unlink()
    (OUT / f"{name}-{ver}.svg").write_text(content, encoding="utf-8")
    readme = re.sub(rf"\./assets/{name}(-\w+)?\.svg(\?v=\w+)?", f"./assets/{name}-{ver}.svg", readme)
    # the README alt text repeats the panel's own label, so the two never drift apart
    label = re.search(r'aria-label="([^"]*)"', content).group(1)
    readme = re.sub(rf'(<img src="\./assets/{name}-{ver}\.svg"[^>]*? alt=")[^"]*"', lambda m: m.group(1) + label + '"', readme)
    print("wrote", name, ver)
README.write_text(readme, encoding="utf-8", newline="\n")
