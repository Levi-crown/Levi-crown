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
.o{{fill:#f0883e}} .r{{fill:{RED}}} .g{{fill:{GRN}}} .y{{fill:{YEL}}} .bl{{fill:{BLU}}} .m{{fill:{MAG}}} .c{{fill:{CYN}}}
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


# official logo paths (Simple Icons, CC0; Android robot from its brand artwork), read from tools/logos
LOGOS = {p.stem: re.search(r' d="([^"]+)"', p.read_text(encoding="utf-8")).group(1)
         for p in (Path(__file__).parent / "logos").glob("*.svg")}


def mascot():
    """A shaded, 3D-looking Tux in a purple beanie (GitHub mark) and tee (Windows logo) holding the Apple and Android logos, the Kali dragon glowing behind.
    Drawn in a 250 x 240 box. The logos are extruded (stacked offset copies); only the eyes move (Tux blinks)."""
    def radial(id_, stops, cx=".35", cy=".3", r=".75"):
        return (f'<radialGradient id="{id_}" cx="{cx}" cy="{cy}" r="{r}">'
                + "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops) + "</radialGradient>")

    def linear(id_, stops, x2="1", y2="1"):
        return (f'<linearGradient id="{id_}" x2="{x2}" y2="{y2}">'
                + "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops) + "</linearGradient>")

    defs = ("<defs>"
            + radial("mBody", [(0, "#3e444d"), (.45, "#16191d"), (1, "#000000")])
            + radial("mFace", [(0, "#ffffff"), (.65, "#e3e8ee"), (1, "#a9b2bc")], cx=".42", cy=".35")
            + radial("mEye", [(0, "#ffffff"), (.7, "#eef1f4"), (1, "#a7b0ba")], cx=".4", cy=".35")
            + radial("mGold", [(0, "#ffd889"), (.55, "#f2a51f"), (1, "#a86200")], cx=".4", cy=".3")
            + radial("mGlow", [(0, "#367bf0"), (.55, "#1d4ea6"), (1, BG)], cx=".5", cy=".5", r=".5")
            + radial("mShirt", [(0, "#b58cf5"), (.55, "#7646d0"), (1, "#3a1a78")], cx=".35", cy=".2", r=".9")
            + linear("mApple", [(0, "#ffffff"), (.5, "#d3d9e0"), (1, "#8d97a2")])
            + linear("mDroid", [(0, "#7cf5b4"), (.5, "#3ddc84"), (1, "#169a52")])
            + '<linearGradient id="mWin" gradientUnits="userSpaceOnUse" x1="107" y1="146" x2="143" y2="182"><stop offset="0" stop-color="#4cc2ff"/><stop offset="1" stop-color="#0067c0"/></linearGradient>'
            + linear("mKali", [(0, "#6aa8ff"), (1, "#1d4ea6")])
            + '<filter id="mDrop" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="4" stdDeviation="3.5" flood-color="#000" flood-opacity=".55"/></filter>'
            + '<filter id="mBlur"><feGaussianBlur stdDeviation="5"/></filter>'
            + f'<path id="mA" transform="translate(12 126) scale(2.2)" d="{LOGOS["apple"]}"/>'
            + f'<path id="mD" transform="translate(176 122) scale(.48)" d="{LOGOS["android"]}"/>'
            + "</defs>")
    # only the eyes move
    css = ("@keyframes wink{0%,90%,100%{transform:scaleY(1)}94%{transform:scaleY(.1)}}"
           ".wink{transform-box:fill-box;transform-origin:center;animation:wink 4s infinite}")

    def extrude(ref, face, side, depth=4):
        # stacked copies, darkest at the back, give the flat logo a thickness; the face sits on top
        layers = "".join(f'<use href="#{ref}" transform="translate({i * .5:.1f} {i * .7:.1f})" fill="{side}"/>' for i in range(depth, 0, -1))
        return f'<g filter="url(#mDrop)">{layers}<use href="#{ref}" fill="url(#{face})"/></g>'

    backdrop = (f'<circle cx="125" cy="112" r="112" fill="url(#mGlow)" opacity=".55"/>'
                f'<path transform="translate(-4 -14) scale(10.8)" d="{LOGOS["kali"]}" fill="url(#mKali)" opacity=".95"/>')
    body = "url(#mBody)"
    shirt = "url(#mShirt)"

    # arms cradle the logos: each flipper leaves the shoulder from behind the torso (so the sleeve grows out of
    # the side seam), runs in front of the logo's base and its tip curls up the outer side, so the logo rests
    # in the crook of the arm. The right arm is the left mirrored.
    def mirror(d):
        return re.sub(r"(-?[\d.]+) (-?[\d.]+)", lambda m: f"{250 - float(m.group(1)):g} {m.group(2)}", d)

    arm_l = "M92 132C66 140 62 172 48 182C36 188 26 180 22 168"
    arm_ps = (arm_l, mirror(arm_l))
    arms = ('<g filter="url(#mDrop)" fill="none" stroke-linecap="round">'
            + "".join(f'<path d="{d}" stroke="{body}" stroke-width="15"/>'
                      # a soft rim light along the top of the flipper gives it volume
                      f'<path d="{d}" stroke="#fff" stroke-opacity=".1" stroke-width="4" transform="translate(0 -3)"/>'
                      # short sleeve: the first stretch of the same path in shirt colour, with a dark hem
                      f'<path d="{d}" pathLength="1" stroke-dasharray=".3 1" stroke="{shirt}" stroke-width="20" stroke-linecap="butt"/>'
                      f'<path d="{d}" pathLength="1" stroke-dasharray="0 .29 .012 1" stroke="#2a1158" stroke-width="20" stroke-linecap="butt"/>'
                      for d in arm_ps) + "</g>")
    tux = (f'<ellipse cx="125" cy="228" rx="74" ry="8" fill="#000" opacity=".5" filter="url(#mBlur)"/>'
           f'<g filter="url(#mDrop)">'
           f'<ellipse cx="125" cy="152" rx="53" ry="68" fill="{body}"/>'
           # the tee follows the body's curve (clipped to the torso); the head, drawn after it, sits in a ribbed
           # crew-neck collar whose lower arc shows below the chin, over a soft shadow the head casts on the tee
           f'<clipPath id="mTorso"><ellipse cx="125" cy="152" rx="53" ry="68"/></clipPath><g clip-path="url(#mTorso)">'
           f'<path d="M60 80H190V194Q125 212 60 194z" fill="{shirt}"/>'
           f'<path d="M90 120Q81 128 77 140M160 120Q169 128 173 140" fill="none" stroke="#2a1158" stroke-opacity=".4" stroke-width="1.5"/>'
           f'<ellipse cx="125" cy="131" rx="36" ry="9" fill="#1c0b40" opacity=".3" filter="url(#mBlur)"/>'
           f'<ellipse cx="125" cy="94" rx="41" ry="38" fill="none" stroke="#7446cc" stroke-width="7"/>'
           f'<ellipse cx="125" cy="94" rx="44.5" ry="41.5" fill="none" stroke="#3a1a78" stroke-opacity=".45" stroke-width="1"/>'
           f'<path d="M66 193Q125 210 184 193" fill="none" stroke="#2a1158" stroke-width="2.5"/>'
           f'<path d="M80 130c-4 20-4 44 2 62M170 130c4 20 4 44-2 62" fill="none" stroke="#000" stroke-opacity=".25" stroke-width="3"/></g>'
           + "".join(f'<rect x="{107 + dx}" y="{146 + dy}" width="17" height="17" rx="1" fill="url(#mWin)"/>' for dx in (0, 19) for dy in (0, 19))
           + f'<ellipse cx="125" cy="92" rx="38" ry="36" fill="{body}"/>'
           f'<path d="M100 98c0-16 10-25 25-25s25 9 25 25c0 13-11 21-25 21s-25-8-25-21z" fill="url(#mFace)"/>'
           f'<g class="wink"><ellipse cx="115" cy="92" rx="7" ry="9" fill="url(#mEye)"/><ellipse cx="135" cy="92" rx="7" ry="9" fill="url(#mEye)"/>'
           f'<ellipse cx="116.5" cy="94" rx="3.4" ry="4.4" fill="#111"/><ellipse cx="133.5" cy="94" rx="3.4" ry="4.4" fill="#111"/>'
           f'<circle cx="117.6" cy="92.4" r="1.2" fill="#fff"/><circle cx="134.6" cy="92.4" r="1.2" fill="#fff"/></g>'
           f'<path d="M108 106c9-7 25-7 34 0-4 9-12 13-17 13s-13-4-17-13z" fill="url(#mGold)"/>'
           f'<path d="M111 107c8 3 20 3 28 0" fill="none" stroke="#8a5200" stroke-width="1.2"/>'
           f'<ellipse cx="102" cy="216" rx="24" ry="10" fill="url(#mGold)"/><ellipse cx="148" cy="216" rx="24" ry="10" fill="url(#mGold)"/>'
           # knit beanie in the tee's purple: a domed crown over the head, a ribbed fold-up cuff across the brow
           # with the GitHub mark on its front. Clipped to the head plus a dome above it, so it hugs the head and
           # nothing sticks out past its sides
           f'<clipPath id="mHat"><ellipse cx="125" cy="92" rx="38.5" ry="36.5"/><ellipse cx="125" cy="72" rx="31" ry="33"/></clipPath>'
           f'<g clip-path="url(#mHat)"><path d="M80 86V30H170V86Z" fill="{shirt}"/>'
           f'<path d="M106 44Q104 60 104 72M125 40V72M144 44Q146 60 146 72" fill="none" stroke="#2a1158" stroke-opacity=".3" stroke-width="1.5"/>'
           f'<clipPath id="mCuff"><path d="M83 69Q125 58 167 69L168 86Q125 75 82 86Z"/></clipPath>'
           f'<g clip-path="url(#mCuff)"><rect x="80" y="55" width="90" height="35" fill="#6a3cc4"/>'
           + "".join(f'<path d="M{x} 55V90" stroke="#2a1158" stroke-opacity=".35" stroke-width="1.2"/>' for x in range(86, 168, 5))
           + f'<rect x="80" y="55" width="90" height="35" fill="url(#mShirt)" opacity=".35"/></g>'
           f'<path d="M83 69Q125 58 167 69" fill="none" stroke="#2a1158" stroke-opacity=".5" stroke-width="1"/></g>'
           f'<path transform="translate(118.2 66.8) scale(.57)" d="{LOGOS["github"]}" fill="#f0f3f6"/>'
           f'</g>')
    logos = extrude("mA", "mApple", "#6b7480") + extrude("mD", "mDroid", "#0f7a3f")
    return f"<style>{css}</style>{defs}{backdrop}{logos}{arms}{tux}"


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
                   f'followers{{totalCount}} repositories(ownerAffiliations:OWNER,privacy:PUBLIC,first:100){{totalCount nodes{{name stargazerCount}}}}}}}}')
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
    followers = user["followers"]["totalCount"]
    # contributions per calendar month, the last 12 months
    months = [((now.year * 12 + now.month - 1 - k) // 12, (now.month - 1 - k) % 12 + 1) for k in range(11, -1, -1)]
    per = dict.fromkeys(months, 0)
    for d, n in days:
        if (d.year, d.month) in per:
            per[d.year, d.month] += n
    series = [per[m] for m in months]

    weeks = coll["contributionCalendar"]["weeks"]
    gap = 3
    step = (W - 72 + gap) / len(weeks)  # heatmap spans the contributions panel's inner width
    cell = round(step - gap, 1)
    # btop-style layout: three small monitor panels, then one panel holding the monthly graph and the heatmap
    by, bh, bw = TOP + 24, 92, (W - 48 - 2 * 12) / 3
    cy0 = by + bh + 18  # contributions panel top
    py0, ph = cy0 + 30, 56  # plot top and height
    py1 = py0 + ph
    top = py1 + 30  # heatmap top, under the month labels
    h = round(top + 7 * step + 52)
    b = frame(h)
    b += prompt(24, TOP, 0.1, [("gh", "g"), (f" stats {USER}", "t")], 0.3, 0.6, "g")
    b.append("<style>@keyframes gy{from{transform:scaleY(0)}}@keyframes gx{from{transform:scaleX(0)}}"
             "@keyframes pulse{50%{opacity:.4}}</style>")

    def grow(axis, t):
        origin = "bottom" if axis == "y" else "left"
        return f"transform-box:fill-box;transform-origin:{origin};animation:g{axis} .6s cubic-bezier(.2,.7,.2,1) {t:.2f}s both"

    def panel(x, y, w, hh, t, title, cls, value="", note=""):
        """A btop panel: thin rounded border with the title (and an optional note on the right) set into its top edge."""
        out = [f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{hh}" rx="5" fill="none" stroke="{LINE}"/>']
        parts = [(title, f"{cls} b")] + ([(f" {value}", "h b")] if value else [])
        n = len("".join(q for q, _ in parts)) + 2
        out.append(f'<rect x="{x + 10:.1f}" y="{y - 7}" width="{n * cw(12):.1f}" height="14" fill="{BG}"/>')
        out.append(text(x + 10 + cw(12), y + 4, parts, fs=12))
        if note:
            nw = (len(note) + 2) * cw(11)
            out.append(f'<rect x="{x + w - 10 - nw:.1f}" y="{y - 7}" width="{nw:.1f}" height="14" fill="{BG}"/>')
            out.append(text(x + w - 10 - nw + cw(11), y + 4, [(note, "d")], fs=11))
        return f'<g class="a" style="{appear(t, 0.25)}">{"".join(out)}</g>'

    # ---- activity: htop meters for the last year's commits, pull requests and issues (log scale, so the small
    # counts still show next to the commits)
    x1 = 24
    b.append(panel(x1, by, bw, bh, 0.9, "activity", "c", note="1y"))
    act = [("commits", coll["totalCommitContributions"], "g"), ("PRs", coll["totalPullRequestContributions"], "bl"),
           ("issues", coll["totalIssueContributions"], "m")]
    slots = 19  # meter width in characters
    top_a = max(v for _, v, _ in act) or 1
    mx = x1 + 12 + 8 * cw(11)
    for i, (lab, v, cls) in enumerate(act):
        y, t = by + 30 + i * 22, 1.1 + i * 0.12
        k = round(slots * math.log1p(v) / math.log1p(top_a)) if v else 0
        num = f"{v:,}"
        b.append(text(x1 + 12, y, [(lab, "d")], fs=11, cls="a", style=appear(t, 0.2)))
        b.append(text(mx, y, [("[", "d"), (" " * slots, "t"), ("]", "d")], fs=11, cls="a", style=appear(t, 0.2)))
        if k:
            b.append(text(mx + cw(11), y, [("|" * k, cls)], fs=11, style=grow("x", t + 0.1)))
        b.append(text(x1 + bw - 12 - len(num) * cw(11), y, [(num, "h b")], fs=11, cls="a", style=appear(t + 0.5, 0.2)))

    # ---- streak: the last 30 days as bars; the running streak glows orange and breathes
    x2 = x1 + bw + 12
    b.append(panel(x2, by, bw, bh, 1.0, "streak", "o", f"{cur}d", f"best {best[0]}d"))
    last30 = days[-30:]
    end = len(last30) - 1 - (bool(last30) and last30[-1][1] == 0)  # today only counts once it has a contribution
    top_s = max((n for _, n in last30), default=0) or 1
    sw, base = (bw - 24) / max(1, len(last30)), by + bh - 12
    for i, (d, n) in enumerate(last30):
        hh = 3 if n == 0 else 8 + 46 * math.log1p(n) / math.log1p(top_s)
        live = end - cur < i <= end
        fill = LINE if n == 0 else "#f0883e" if live else "#26a641"
        st = grow("y", 1.2 + i * 0.025) + (f",pulse 1.8s ease-in-out {2.2 + i * 0.05:.2f}s infinite" if live else "")
        b.append(f'<rect x="{x2 + 12 + i * sw:.1f}" y="{base - hh:.1f}" width="{sw - 2:.1f}" height="{hh:.1f}" rx="1.5" '
                 f'fill="{fill}" style="{st}"/>')

    # ---- stars: the most-starred repos as bars
    x3 = x2 + bw + 12
    b.append(panel(x3, by, bw, bh, 1.1, "stars", "y", f"{stars:,}", f"{repos['totalCount']} repos · {followers} followers"))
    starred = sorted((r for r in repos["nodes"] if r["stargazerCount"]), key=lambda r: -r["stargazerCount"])[:4]
    top_r = starred[0]["stargazerCount"] if starred else 1
    bx0, bx1 = x3 + 12 + 13 * cw(11), x3 + bw - 12 - 4 * cw(11) - 4
    for i, r in enumerate(starred):
        y, t = by + 28 + i * 17, 1.3 + i * 0.12
        name = r["name"] if len(r["name"]) <= 12 else r["name"][:11] + "…"
        num = f"{r['stargazerCount']:,}"
        b.append(text(x3 + 12, y, [(name, "t")], fs=11, cls="a", style=appear(t, 0.2)))
        b.append(f'<rect x="{bx0:.1f}" y="{y - 7}" width="{(bx1 - bx0) * r["stargazerCount"] / top_r:.1f}" height="6" rx="3" '
                 f'fill="{YEL}" style="{grow("x", t + 0.1)}"/>')
        b.append(text(x3 + bw - 12 - len(num) * cw(11), y, [(num, "h b")], fs=11, cls="a", style=appear(t + 0.5, 0.2)))
    if not starred:
        b.append(text(x3 + 12, by + 50, [("no stars yet", "d")], fs=11, cls="a", style=appear(1.3, 0.2)))

    b.append(panel(24, cy0, W - 48, h - cy0 - 14, 1.4, "contributions", "g", f"{total:,}", f"since {since:%b %Y}"))

    # ---- monthly contributions: gridlines, then the line draws itself, then area and dots
    tg = 1.6
    top_v = max(series) or 1
    mag = 10 ** math.floor(math.log10(top_v))
    ymax = next(f * mag for f in (1, 2, 2.5, 5, 10) if f * mag >= top_v)
    px0, px1 = 44, W - 44
    xs = [px0 + i * (px1 - px0) / (len(series) - 1) for i in range(len(series))]
    ys = [py1 - v / ymax * ph for v in series]
    gst = appear(tg, 0.2)
    for f in (0, 0.5, 1):
        gy = py1 - f * ph
        b.append(f'<line class="a" x1="{px0}" y1="{gy:.1f}" x2="{px1}" y2="{gy:.1f}" stroke="{LINE}" stroke-dasharray="2 4" style="{gst}"/>')
    for i, (yy, mm) in enumerate(months):
        lab = dt.date(yy, mm, 1).strftime("%b")
        b.append(text(xs[i] - len(lab) * cw(10) / 2, py1 + 16, [(lab, "d")], fs=10, cls="a", style=gst))
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

    x0 = 36
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
    lx = W - 36 - len(levels) * (cell + gap) - 4 - 4 * cw(12)
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
