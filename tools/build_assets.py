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
  *{{animation:none!important}} .a{{opacity:1!important}} .draw{{stroke-dashoffset:0!important}} .cv,.cur,.game,.ping{{display:none}}
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


# ---------------------------------------------------------------- neofetch
def neofetch():
    # Tux as pixel art: ASCII penguins drift out of line when GitHub falls back to another font
    tux = """
.......KKKKKK.......
......KKKKKKKK......
.....KKKKKKKKKK.....
.....KEEKKKKEEK.....
.....KEPKKKKPEK.....
.....KEEKKKKEEK.....
.....KKYYYYYYKK.....
....KKYYYYYYYYKK....
....KKKYYYYYYKKK....
...KKKWWYYYYWWKKK...
...KKWWWWWWWWWWKK...
..KKWWWWWWWWWWWWKK..
..KKWWWWWWWWWWWWKK..
.KKWWWWWWWWWWWWWWKK.
.KKWWWWWWWWWWWWWWKK.
.KKWWWWWWWWWWWWWWKK.
.KKWWWWWWWWWWWWWWKK.
..KKWWWWWWWWWWWWKK..
.YYYKWWWWWWWWWWKYYY.
YYYYYKWWWWWWWWKYYYYY
YYYYYYKKKKKKKKYYYYYY
.YYYYY........YYYYY.
""".split()
    # Tux wears a GitHub tee (belly rows become shirt), holds the Apple logo and the Android robot,
    # and the Kali dragon coils behind him; layers are painted back to front
    tux = [row.replace("W", "S") if 10 <= r <= 19 else row for r, row in enumerate(tux)]
    octocat = [".O...O.", ".OOOOO.", "OOOOOOO", "OO.O.OO", "OOOOOOO", ".OO.OO."]
    apple = ["......A..", ".....AA..", ".....A...", ".AAA.AAA.", "AAAAAAAAA", "AAAAAAA..", "AAAAAA...",
             "AAAAAAA..", "AAAAAAAAA", ".AAAAAAA.", "..AA.AA.."]
    android = [".G.....G.", "..GGGGG..", ".GGGGGGG.", ".GgGGGgG.", ".GGGGGGG.", ".........",
               "GGGGGGGGG", "GGGGGGGGG", ".GGGGGGG.", "..G...G.."]
    head = [".........d..d.", "........dDDdD.", "....DDDDDDDDD.", "..DDDDDeDDDDD.",
            "DDDDDDDDDDDDd.", ".ddDDDDDDDDDd.", "....dd..DDDDd.", "........DDDDd."]
    neck = [".DDDDdd", ".DDDDd.", "DDDDdd.", "DDDDd..", "DDDd...", "DDDd..."]
    shoulder = ["DDDDDDDD", "DDDDDDd.", "DDDDDd..", "DDDd...."]  # neck dives behind Tux
    wing = [".d..........", ".Dd.........", ".DDd...d....", ".DDDd.dD....", ".DDDDdDD....", ".DDDDDDDd...",
            "..DDDDDDDD..", "...DDDDDDDDDDDDD", "....DDDDDDDDDDDD", "......DDDDDDDDDD"]
    tail = ["..........d", ".........dD", "DDDDDDDDDDd", "dDDDDDDDdd."]  # out from behind the feet, curling up
    layers = [(head, 23, 0), (neck, 30, 8), (shoulder, 25, 13), (wing, 0, 2), (tail, 26, 28),
              (tux, 9, 9), (octocat, 15, 20), (apple, 2, 17), (android, 27, 18)]
    art_colors = {"K": "#3d444d", "E": HI, "P": BG, "W": HI, "Y": YEL, "S": "#161b22", "O": HI,
                  "D": "#367bf0", "d": "#1d4ea6", "e": RED, "A": "#c9d1d9", "G": "#3ddc84", "g": BG}
    art = {}
    for sprite, ox, oy in layers:
        for r, row in enumerate(sprite):
            for c, ch in enumerate(row):
                if ch != ".":
                    art[oy + r, ox + c] = art_colors[ch]
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
    px = 7
    art_h = max(r for r, _ in art) + 1
    # centered on the output block, from the user@host line down to the color bar
    tx, ty = 24, y0 + (len(rows) * 24 - 48) / 2 - art_h * px / 2
    cells = []
    for (r, c), color in sorted(art.items()):
        if (r, c - 1) in art and art[r, c - 1] == color:
            continue  # already covered by the run that starts further left
        n = 1
        while art.get((r, c + n)) == color:
            n += 1
        cells.append(f'<rect x="{tx + c * px}" y="{ty + r * px:.1f}" width="{n * px}" height="{px}" fill="{color}"/>')
    cells = "".join(cells)
    b.append(f'<g class="a" shape-rendering="crispEdges" style="{appear(0.95, 0.05)}">{cells}</g>')
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
    # two columns of key / value / note, typed out row by row
    rows = [
        [("contributions", f"{total:,}", f"since {since:%b} {since.year}"), ("stars", f"{stars:,}", "")],
        [("current streak", plural(cur, "day"), ""), ("followers", f"{user['followers']['totalCount']:,}", "")],
        [("longest streak", plural(best[0], "day"), f"{day(best[1])} - {day(best[2])}" if best[0] else ""),
         ("public repos", f"{repos['totalCount']}", "")],
        [("commits", f"{coll['totalCommitContributions']:,}", "last year"),
         ("PRs / issues", f"{coll['totalPullRequestContributions']:,} / {coll['totalIssueContributions']:,}", "")],
    ]
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
    gtop = start + len(rows) * 26 + 14  # graph caption baseline
    py0, ph = gtop + 18, 96  # plot top and height
    py1 = py0 + ph
    top = py1 + 44  # heatmap top, under the month labels
    h = round(top + 7 * step + 42)
    b = frame(h)
    b += prompt(24, TOP, 0.1, [("gh", "g"), (f" stats {USER}", "t")], 0.3, 0.6, "g")
    for i, row in enumerate(rows):
        y, st = start + i * 26, appear(1.0 + i * 0.12, 0.01)
        for (k, v, note), (kx, kw) in zip(row, [(24, 17), (448, 15)]):
            b.append(text(kx, y, [(k, "bl b")], cls="a", style=st))
            b.append(text(kx + kw * cw(14), y, [(v, "h b")], cls="a", style=st))
            if note:
                b.append(text(kx + 30 * cw(14), y, [(note, "d")], cls="a", style=st))

    # ---- monthly contributions: gridlines, then the line draws itself, then area and dots
    tg = 1.0 + len(rows) * 0.12
    top_v = max(series) or 1
    mag = 10 ** math.floor(math.log10(top_v))
    ymax = next(f * mag for f in (1, 2, 2.5, 5, 10) if f * mag >= top_v)
    px0, px1 = 24 + 6 * cw(11), W - 30
    xs = [px0 + i * (px1 - px0) / (len(series) - 1) for i in range(len(series))]
    ys = [py1 - v / ymax * ph for v in series]
    gst = appear(tg, 0.2)
    b.append(text(24, gtop, [("contributions per month", "d")], fs=12, cls="a", style=gst))
    for f in (0, 0.5, 1):
        gy = py1 - f * ph
        label = f"{ymax * f:g}"
        b.append(f'<line class="a" x1="{px0}" y1="{gy:.1f}" x2="{px1}" y2="{gy:.1f}" stroke="{LINE}" stroke-dasharray="2 4" style="{gst}"/>')
        b.append(text(px0 - 8 - len(label) * cw(11), gy + 4, [(label, "d")], fs=11, cls="a", style=gst))
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
    b.append(text(24, ly + 9, [(f"{user['last']['contributionCalendar']['totalContributions']:,} contributions in the last year", "d")], fs=12))
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
