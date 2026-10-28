"""Generate the terminal-themed SVG assets for the Levi-crown profile README.

usage: python tools/build_assets.py assets   (also updates image links in README.md)
"""
import base64
import colorsys
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ICONS = Path(__file__).parent / "icons"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

# GitHub dark background, GitHub "dimmed" ANSI palette for terminal colors
BG, BAR, LINE = "#0d1117", "#161b22", "#30363d"
TXT, DIM, HI = "#adbac7", "#768390", "#cdd9e5"
RED, GRN, YEL, BLU, MAG, CYN = "#e5534b", "#57ab5a", "#daaa3f", "#539bf5", "#b083f0", "#39c5cf"
W = 840
FONT = "'JetBrains Mono','Fira Code','Cascadia Mono',Consolas,'DejaVu Sans Mono',Menlo,monospace"

# brand colors, lightened only where the official color disappears on a dark background
BRAND = {
    "python": "#4B8BBE", "openjdk": "#F89820", "csharp": "#B07CD8", "gnubash": "#4EAA25", "claude": "#D97757", "openai": HI,
    "nousresearch": HI, "kimi": HI, "opencv": "#8C7CF0", "mediapipe": "#14A8B8",
    "numpy": "#4DABCF", "espressif": "#E7352C", "arduino": "#00979D", "raspberrypi": "#C51A4A",
    "kalilinux": "#4C8DF6", "archlinux": "#D64545", "parrotsecurity": "#15E0ED",
    "android": "#3DDC84", "lineageos": "#23A9A9", "magisk": "#00AF9C", "cisco": "#1BA0D7", "wireshark": "#3A9BD9", "vscode": "#23A9F2", "visualstudio": "#A178DF", "androidstudio": "#3DDC84", "windows11": "#2D8FE6", "powershell": "#5391FE", "platformio": "#F5822A",
}

BASE_CSS = f"""
text{{font-family:{FONT};white-space:pre}}
.t{{fill:{TXT}}} .d{{fill:{DIM}}} .h{{fill:{HI}}} .b{{font-weight:700}}
.r{{fill:{RED}}} .g{{fill:{GRN}}} .y{{fill:{YEL}}} .bl{{fill:{BLU}}} .m{{fill:{MAG}}} .c{{fill:{CYN}}}
.a{{opacity:0}}
@keyframes in{{to{{opacity:1}}}}
@keyframes blink{{0%{{opacity:1}}50%{{opacity:0}}}}
@keyframes vis{{0%,100%{{opacity:1}}}}
@media (prefers-reduced-motion:reduce){{
  *{{animation:none!important}} .a{{opacity:1!important}} .cv,.cur{{display:none}}
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


def frame(h, title=None):
    out = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="6" fill="{BG}" stroke="{LINE}"/>']
    if title is not None:
        out.append(f'<path d="M0.5 32V6.5a6 6 0 0 1 6-6h{W - 13}a6 6 0 0 1 6 6V32z" fill="{BAR}"/>')
        out.append(f'<line x1="0.5" y1="32" x2="{W - 0.5}" y2="32" stroke="{LINE}"/>')
        for i, c in enumerate((RED, YEL, GRN)):
            out.append(f'<circle cx="{20 + i * 18}" cy="16.5" r="5.5" fill="{c}" fill-opacity="0.85"/>')
        tl = len(title) * cw(12)
        out.append(text(W / 2 - tl / 2, 20.5, [(title, "d")], fs=12))
    return out


def svg(h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
            f'role="img" aria-label="{escape(label)}"><title>{escape(label)}</title>'
            f'<style>{BASE_CSS}</style>' + "".join(body) + "</svg>")


# Kali's default zsh prompt colors for a normal user
KALI_TOP = [("(", "g"), ("levi㉿kali", "bl b"), (")-[", "g"), ("~", "h b"), ("]", "g")]


def kali_prompt(x, y, t, cmd=None, type_start=None, type_dur=None, kid=""):
    """Two-line Kali zsh prompt. Optionally types `cmd` (list of parts) with a stepping cover + cursor."""
    # the ┌── └─ corner is drawn as a path: box-drawing glyphs come out squashed under textLength
    c = cw(14)
    corner = (f'<path class="a" d="M{x + 3 * c - 1:.1f} {y - 5}H{x + c / 2:.1f}V{y + 17}H{x + 2 * c - 1:.1f}" '
              f'fill="none" stroke="{GRN}" stroke-width="1.4" style="{appear(t, 0.01)}"/>')
    out = [corner, text(x + 3 * c, y, KALI_TOP, cls="a", style=appear(t, 0.01)),
           text(x + 2 * c, y + 22, [("$ ", "bl b")], cls="a", style=appear(t, 0.01))]
    if cmd:
        cx = x + 4 * cw(14)
        n = len("".join(p for p, _ in cmd))
        dist = n * cw(14)
        out.append(text(cx, y + 22, cmd))
        out.append(f"<style>@keyframes ty{kid}{{to{{transform:translateX({dist:.1f}px)}}}}</style>")
        mv = f"animation:ty{kid} {type_dur}s steps({n}) {type_start}s forwards"
        out.append(f'<rect class="cv" x="{cx - 1}" y="{y + 7}" width="{dist + 4:.1f}" height="20" fill="{BG}" style="{mv}"/>')
        out.append(f'<g style="{mv}"><rect class="cur" x="{cx}" y="{y + 10}" width="{cw(14):.1f}" height="16" '
                   f'fill="{TXT}" opacity="0" style="animation:vis {type_dur + 0.2}s linear {type_start}s"/></g>')
    return out


# full-color official logos; dark parts swapped for their light-background variant
COLOR_FIX = {
    "bash": {"#293138": "#d1d7e0"},
    "kimi": {"currentColor": HI},
    "mysql": {"#00618A": "#5FB0D6"},
}


# official logos that only exist as raster images: (file, viewBox crop)
IMAGES = {"nmap": ("nmap.png", "0 34 256 96")}  # the Nmap eye, without the wordmark


def icon(name, x, y, size=20):
    if name in IMAGES:
        file, crop = IMAGES[name]
        data = base64.b64encode((ICONS / "img" / file).read_bytes()).decode()
        # box matches the crop's aspect ratio, so nothing outside the crop can show
        cx_, cy_, cw_, ch_ = map(float, crop.split())
        bw = size + 6
        bh = bw * ch_ / cw_
        return (f'<svg x="{x - 3}" y="{y + (size - bh) / 2:.1f}" width="{bw}" height="{bh:.1f}" viewBox="{crop}">'
                f'<image href="data:image/png;base64,{data}" width="256" height="256"/></svg>')
    if name == "oracle":
        # the Oracle wordmark is unreadable at icon size; use its red "O" ring (oracle.com's site icon)
        return (f'<ellipse cx="{x + size / 2}" cy="{y + size / 2}" rx="{size / 2 - 1.5}" ry="{size / 2 - 5}" '
                f'fill="none" stroke="#C74634" stroke-width="3.2"/>')
    color = ICONS / "color" / f"{name}.svg"
    if color.exists():
        raw = color.read_text(encoding="utf-8")
        for a, b in COLOR_FIX.get(name, {}).items():
            raw = raw.replace(f'"{a}"', f'"{b}"')
        vb = re.search(r'viewBox="([^"]+)"', raw).group(1)
        root = re.search(r"<svg[^>]*>", raw).group(0)
        keep = "".join(f' {m.group(0)}' for m in re.finditer(r'\b(?:fill|fill-rule)="[^"]*"', root))
        inner = re.sub(r"^.*?<svg[^>]*>|</svg>\s*$", "", raw.strip(), flags=re.S)
        inner = f"<g{keep}>{inner}</g>"
        inner = re.sub(r"<title>.*?</title>", "", inner)
        # gradient ids would collide between logos once inlined
        inner = re.sub(r'id="([^"]+)"', rf'id="{name}-\1"', inner)
        inner = re.sub(r"url\(#([^)]+)\)", rf"url(#{name}-\1)", inner)
        inner = re.sub(r'href="#([^"]+)"', rf'href="#{name}-\1"', inner)
        return (f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="{vb}" '
                f'xmlns:xlink="http://www.w3.org/1999/xlink">{inner}</svg>')
    raw = (ICONS / f"{name}.svg").read_text(encoding="utf-8")
    vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', raw)
    s = size / float(vb.group(1))
    rule = ' fill-rule="evenodd"' if 'fill-rule="evenodd"' in raw else ""
    paths = "".join(re.sub(r'\sfill="[^"]*"', "", p)
                    for p in re.findall(r"<path[^>]*?(?:/>|>.*?</path>)", raw, flags=re.S))
    return f'<g transform="translate({x} {y}) scale({s:.4f})" fill="{BRAND[name]}"{rule}>{paths}</g>'


def hsl(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, l, s)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


# ---------------------------------------------------------------- hero
def hero():
    banner = [
        "██╗     ███████╗██╗   ██╗██╗",
        "██║     ██╔════╝██║   ██║██║",
        "██║     █████╗  ██║   ██║██║",
        "██║     ██╔══╝  ╚██╗ ██╔╝██║",
        "███████╗███████╗ ╚████╔╝ ██║",
    ]
    x = 24
    h = 380
    b = frame(h, "levi@kali: ~")
    b += kali_prompt(x, 62, 0.2, [("figlet", "g"), (" levi ", "t"), ("|", "t"), (" lolcat", "g")], 0.6, 1.2, "a")
    # lolcat: hue drifts along a diagonal; blocks drawn as rects since box glyphs render unevenly
    cx, cy, top = 12, 17, 112
    for i, ln in enumerate(banner):
        shadow, solid = [], []
        for c, ch in enumerate(ln):
            if ch != "█":
                continue
            hue = 195 + c * 7 + i * 6
            px, py = x + c * cx, top + i * cy
            shadow.append(f'<rect x="{px + 4}" y="{py + 4}" width="{cx + 0.6}" height="{cy + 1}" fill="{hsl(hue, 0.55, 0.2)}"/>')
            solid.append(f'<rect x="{px}" y="{py}" width="{cx + 0.6}" height="{cy + 1}" fill="{hsl(hue, 0.62, 0.64)}"/>')
        b.append(f'<g class="a" shape-rendering="crispEdges" style="{appear(1.95 + i * 0.06, 0.05)}">'
                 + "".join(shadow) + "".join(solid) + "</g>")
    b += kali_prompt(x, 240, 2.5, [("whoami", "g")], 2.8, 0.5, "b")
    b.append(text(x, 288, [("Levi", "h b"), (". Full stack dev who lives in the terminal and likes to see how things work.", "t")],
                  cls="a", style=appear(3.45, 0.01)))
    b.append(text(x, 310, [("Still learning, one project at a time.", "d")],
                  cls="a", style=appear(3.55, 0.01)))
    b += kali_prompt(x, 336, 3.8)
    b.append(f'<rect x="{x + 4 * cw(14):.1f}" y="{336 + 22 - 12}" width="{cw(14):.1f}" height="16" fill="{TXT}" '
             f'opacity="0" style="animation:blink 1.1s steps(1) 3.9s infinite"/>')
    return svg(h, b, "Terminal: figlet levi piped to lolcat, whoami. Levi, full stack dev who lives in the terminal. Still learning, one project at a time.")


# ---------------------------------------------------------------- neofetch
def neofetch():
    # classic Tux: gray outline, light eyes, yellow beak and feet
    tux = [
        [("        .--.", "t")],
        [("       |", "t"), ("o_o", "h"), (" |", "t")],
        [("       |", "t"), (":_/", "y"), (" |", "t")],
        [("      //   \\ \\", "t")],
        [("     (|     | )", "t")],
        [("    /'\\_   _/`\\", "t")],
        [("    ", "t"), ("\\___)", "y"), ("=", "t"), ("(___/", "y")],
    ]
    rows = [
        ("Role", "full stack developer"),
        ("OS", "Kali, BlackArch, Parrot OS, Windows, Windows Server"),
        ("Shell", "bash, PowerShell"),
        ("Editor", "Visual Studio Code"),
        ("IDE", "Visual Studio, Android Studio, PlatformIO"),
        ("Language", "Python, JavaScript, TypeScript, Java, C#, PHP"),
        ("Frontend", "React, Vite, Tailwind CSS, HTML, CSS"),
        ("Backend", "Firebase, Supabase, PHP, Docker"),
        ("Database", "MySQL, SQL Server, Oracle, SQLite, MongoDB"),
        ("AI", "Claude, Codex, Hermes, Kimi"),
        ("ML / CV", "OpenCV, MediaPipe, machine learning"),
        ("Android", "AOSP, rooting, custom ROMs, Magisk modules"),
        ("Embedded", "ESP32, Arduino, Raspberry Pi"),
        ("Network", "Cisco Packet Tracer, Nmap, Wireshark"),
        ("Hardware", "PC and phone troubleshooting / repair"),
        ("Security", "ethical hacking (own gear or with permission)"),
        ("Level", "not an expert, still learning"),
    ]
    h = 118 + len(rows) * 24 + 46
    b = frame(h, "neofetch")
    for i, ln in enumerate(tux):
        b.append(text(44, 118 + (len(rows) - 1) * 12 - 63 + i * 21, ln, fs=16))
    ix, vx = 270, 270 + 11 * cw(14)
    b.append(text(ix, 72, [("levi", "bl b"), ("@", "t"), ("Levi-crown", "bl b")]))
    b.append(text(ix, 92, [("-" * 15, "d")]))
    for i, (k, v) in enumerate(rows):
        y = 118 + i * 24
        st = appear(0.3 + i * 0.07, 0.01)
        b.append(text(ix, y, [(k + ":", "bl b")], cls="a", style=st))
        b.append(text(vx, y, v, cls="a", style=st))
    ansi = ["#2d333b", RED, GRN, YEL, BLU, MAG, CYN, TXT]
    for i, c in enumerate(ansi):
        b.append(f'<rect class="a" x="{ix + i * 30}" y="{118 + len(rows) * 24 + 2}" width="30" height="16" fill="{c}" style="{appear(1.1, 0.01)}"/>')
    return svg(h, b, "neofetch: Role full stack developer. OS Kali Linux, BlackArch, Parrot OS, Windows, Windows Server. Network Cisco Packet Tracer, Nmap, Wireshark. Shell bash, PowerShell. Language Python, JavaScript, TypeScript, Java, C#, PHP. Frontend React, Vite, Tailwind CSS, HTML, CSS. Backend Firebase, Supabase, PHP, Docker. Database MySQL, SQL Server, Oracle, SQLite, MongoDB. Editor Visual Studio Code. IDE Visual Studio, Android Studio, PlatformIO. AI Claude, Codex, Hermes, Kimi. "
                     "ML/CV OpenCV, MediaPipe. Android AOSP, rooting, custom ROMs, Magisk modules. Embedded ESP32, Arduino, "
                     "Raspberry Pi. Hardware PC and phone repair. Security ethical hacking. Level: not an expert, still learning.")


# ---------------------------------------------------------------- stack
def stack():
    # 3-column grid of directories
    groups = [
        ("lang/", [("python", "Python"), ("java", "Java"), ("csharp", "C#"), ("bash", "Bash / Shell"), ("powershell", "PowerShell")]),
        ("ai/", [("claude", "Claude"), ("openai", "Codex"), ("nousresearch", "Hermes"), ("kimi", "Kimi")]),
        ("ml-cv/", [("opencv", "OpenCV"), ("mediapipe", "MediaPipe"), ("numpy", "NumPy")]),
        ("embedded/", [("espressif", "ESP32"), ("arduino", "Arduino"), ("raspberrypi", "Raspberry Pi")]),
        ("os/", [("kalilinux", "Kali Linux"), ("archlinux", "BlackArch"), ("parrotsecurity", "Parrot OS"),
                 ("windows11", "Windows"), ("windows11", "Windows Server")]),
        ("android/", [("android", "AOSP"), ("lineageos", "Custom ROMs"), ("magisk", "Magisk modules")]),
    ]
    # full-width sections below the grid, laid out on the same three columns
    wide = [
        ("web/", [("html5", "HTML"), ("css3", "CSS"), ("javascript", "JavaScript"), ("typescript", "TypeScript"),
                  ("react", "React"), ("vitejs", "Vite"), ("tailwindcss", "Tailwind CSS"), ("php", "PHP"), ("docker", "Docker")]),
        ("network/", [("cisco", "Cisco Packet Tracer"), ("nmap", "Nmap"), ("wireshark", "Wireshark")]),
        ("database/", [("mysql", "MySQL"), ("microsoftsqlserver", "Microsoft SQL Server"), ("oracle", "Oracle"),
                       ("sqlite", "SQLite"), ("mongodb", "MongoDB"), ("firebase", "Firebase"), ("supabase", "Supabase")]),
        ("tools/", [("vscode", "Visual Studio Code"), ("visualstudio", "Visual Studio"),
                    ("androidstudio", "Android Studio"), ("platformio", "PlatformIO IDE")]),
    ]
    colw, rowh, top = 264, 34, 74
    row_heights = [26 + max(len(g[1]) for g in groups[r * 3:r * 3 + 3]) * rowh + 22 for r in range(2)]
    wide_heights = [26 + -(-len(items) // 3) * rowh + 22 for _, items in wide]
    h = top + sum(row_heights) + sum(wide_heights) - 10
    b = frame(h)
    b.append(text(24, 38, [("$ ", "bl b"), ("ls", "g"), (" ~/stack", "t")]))
    b.append(f'<line x1="24" y1="54" x2="{W - 24}" y2="54" stroke="{LINE}"/>')
    y0 = top
    for r in range(2):
        for c in range(3):
            label, items = groups[r * 3 + c]
            x = 24 + c * colw
            b.append(text(x, y0 + 14, [(label, "bl b")]))  # ls colors directories bold blue
            for i, (ic, name) in enumerate(items):
                iy = y0 + 30 + i * rowh
                b.append(icon(ic, x, iy))
                b.append(text(x + 30, iy + 14, name))
        y0 += row_heights[r]
    for (label, items), wh in zip(wide, wide_heights):
        b.append(text(24, y0 + 14, [(label, "bl b")]))
        for i, (ic, name) in enumerate(items):
            x, iy = 24 + (i % 3) * colw, y0 + 30 + (i // 3) * rowh
            b.append(icon(ic, x, iy))
            b.append(text(x + 30, iy + 14, name))
        y0 += wh
    return svg(h, b, "Stack. lang: Python, Java, C#, Bash, PowerShell. ai: Claude, Codex, Hermes, Kimi. ml-cv: OpenCV, MediaPipe, NumPy. "
                     "embedded: ESP32, Arduino, Raspberry Pi. os: Kali Linux, BlackArch, Parrot OS, Windows, Windows Server. "
                     "web: HTML, CSS, JavaScript, TypeScript, React, Vite, Tailwind CSS, PHP, Docker. network: Cisco Packet Tracer, Nmap, Wireshark. "
                     "android: AOSP, custom ROMs, Magisk modules. "
                     "database: MySQL, Microsoft SQL Server, Oracle, SQLite, MongoDB, Firebase, Supabase. tools: Visual Studio Code, Visual Studio, Android Studio, PlatformIO IDE.")


# ---------------------------------------------------------------- log
def log():
    done = [
        "wrote my own Magisk modules",
        "hand and face tracking with MediaPipe + OpenCV",
        "ESP32-CAM streaming live video into a machine learning model",
        "full stack web apps with React, Firebase and Supabase",
        "ESP32 / Arduino / Raspberry Pi builds: sensors, wiring and small gadgets",
        "rooted phones, flashed custom ROMs, dug through AOSP",
        "security labs on Kali, BlackArch and Parrot (own gear only)",
        "PC and phone hardware troubleshooting and repair",
    ]
    doing = [
        "going deeper into machine learning",
        "building AOSP from source",
    ]
    h = 74 + len(done) * 26 + 18 + len(doing) * 26 + 10
    b = frame(h)
    b.append(text(24, 38, [("$ ", "bl b"), ("cat", "g"), (" ~/notes/now.log", "t")]))
    b.append(f'<line x1="24" y1="54" x2="{W - 24}" y2="54" stroke="{LINE}"/>')
    y, t = 84, 0.3
    # metasploit-style markers: [+] success, [*] status
    for s in done:
        b.append(text(24, y, [("[+] ", "g b"), (s, "t")], cls="a", style=appear(t, 0.01)))
        y += 26
        t += 0.12
    y += 18
    for s in doing:
        b.append(text(24, y, [("[*] ", "bl b"), (s, "t"), ("  in progress", "y")], cls="a", style=appear(t, 0.01)))
        y += 26
        t += 0.12
    return svg(h, b, "Log. Done: Magisk modules, MediaPipe + OpenCV tracking, ESP32-CAM with machine learning, "
                     "full stack web apps, ESP32/Arduino/Raspberry Pi builds, rooting and custom ROMs, security labs, "
                     "hardware repair. In progress: machine learning, building AOSP from source.")


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
    user = graphql(f'{{user(login:"{USER}"){{createdAt {years} last:contributionsCollection{{{CAL}}} '
                   f'repositories(ownerAffiliations:OWNER,privacy:PUBLIC,first:100){{totalCount nodes{{stargazerCount}}}}}}}}')
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

    rows = [
        ("contributions", f"{total:,}", f"since {since:%b} {since.year}"),
        ("current streak", plural(cur, "day"), ""),
        ("longest streak", plural(best[0], "day"), f"{day(best[1])} - {day(best[2])}" if best[0] else ""),
        ("public repos", f"{repos['totalCount']}", plural(stars, "star")),
    ]
    weeks = user["last"]["contributionCalendar"]["weeks"]
    gap = 3
    step = (W - 48 + gap) / len(weeks)  # heatmap spans the full text width
    cell = round(step - gap, 1)
    top = 84 + len(rows) * 26 + 6
    h = round(top + 7 * step + 42)
    b = frame(h)
    b.append(text(24, 38, [("$ ", "bl b"), ("gh", "g"), (f" stats {USER}", "t")]))
    b.append(f'<line x1="24" y1="54" x2="{W - 24}" y2="54" stroke="{LINE}"/>')
    vx, nx = 24 + 17 * cw(14), 24 + 30 * cw(14)
    for i, (k, v, note) in enumerate(rows):
        y, st = 84 + i * 26, appear(0.3 + i * 0.12, 0.01)
        b.append(text(24, y, [(k, "bl b")], cls="a", style=st))
        b.append(text(vx, y, [(v, "h b")], cls="a", style=st))
        b.append(text(nx, y, [(note, "d")], cls="a", style=st))
    # GitHub's dark-mode contribution greens
    levels = ["#2d333b", "#0e4429", "#006d32", "#26a641", "#39d353"]
    peak = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=0) or 1

    def shade(n):
        return levels[0] if n == 0 else levels[min(4, 1 + 4 * (n - 1) // peak)]

    x0 = 24
    t0 = 0.3 + len(rows) * 0.12
    for wi, w in enumerate(weeks):
        # the first week can start mid-week; place days by weekday
        cells = "".join(f'<rect x="{x0 + wi * step:.1f}" y="{top + ((dt.date.fromisoformat(d["date"]).weekday() + 1) % 7) * step:.1f}" '
                        f'width="{cell}" height="{cell}" rx="2" fill="{shade(d["contributionCount"])}"/>'
                        for d in w["contributionDays"])
        b.append(f'<g class="a" style="{appear(t0 + wi * 0.012, 0.05)}">{cells}</g>')
    ly = round(top + 7 * step + 16)
    cell, gap = 11, 3  # legend swatches stay small
    lx = W - 24 - len(levels) * (cell + gap) - 4 - 4 * cw(12)
    b.append(text(lx - 5 * cw(12), ly + 9, [("less", "d")], fs=12))
    for i, c in enumerate(levels):
        b.append(f'<rect x="{lx + i * (cell + gap)}" y="{ly}" width="{cell}" height="{cell}" rx="2" fill="{c}"/>')
    b.append(text(lx + len(levels) * (cell + gap) + 4, ly + 9, [("more", "d")], fs=12))
    b.append(text(24, ly + 9, [(f"{user['last']['contributionCalendar']['totalContributions']:,} contributions in the last year", "d")], fs=12))
    return svg(h, b, f"GitHub stats. {total:,} contributions since {since:%B %Y}. Current streak {plural(cur, 'day')}, "
                     f"longest streak {plural(best[0], 'day')}. {repos['totalCount']} public repos, {plural(stars, 'star')}.")


README = Path(__file__).parent.parent / "README.md"
readme = README.read_text(encoding="utf-8")
for name, fn in [("hero", hero), ("neofetch", neofetch), ("stack", stack), ("log", log), ("stats", stats)]:
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
    print("wrote", name, ver)
README.write_text(readme, encoding="utf-8", newline="\n")
