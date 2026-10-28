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
    "flask": HI, "vercel": HI, "mqtt": HI, "burpsuite": "#FF6633", "metasploit": "#2596CD",
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


TITLE = "levi@kali: ~"
BAR_H = 34
TOP = BAR_H + 30  # baseline of the first prompt line


def frame(h, title=TITLE):
    """A Linux terminal window: app icon on the left, title centered, minimize / maximize / close on the right."""
    out = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="6" fill="{BG}" stroke="{LINE}"/>',
           f'<path d="M0.5 {BAR_H}V6.5a6 6 0 0 1 6-6h{W - 13}a6 6 0 0 1 6 6V{BAR_H}z" fill="{BAR}"/>',
           f'<line x1="0.5" y1="{BAR_H}" x2="{W - 0.5}" y2="{BAR_H}" stroke="{LINE}"/>']
    # terminal app icon
    out.append(f'<rect x="14.5" y="10.5" width="18" height="14" rx="2.5" fill="none" stroke="{DIM}" stroke-width="1.3"/>'
               f'<path d="M18.5 14.5l3 2.5-3 2.5M23 20.5h5" fill="none" stroke="{TXT}" stroke-width="1.3" '
               f'stroke-linecap="round" stroke-linejoin="round"/>')
    tl = len(title) * cw(12)
    out.append(text(W / 2 - tl / 2, 21.5, [(title, "d")], fs=12))
    cy = BAR_H / 2
    controls = [f'M{W - 86} {cy + 4}h10',  # minimize
                f'M{W - 56} {cy - 5}h10v10h-10z',  # maximize
                f'M{W - 26} {cy - 5}l10 10M{W - 16} {cy - 5}l-10 10']  # close
    out.append(f'<path d="{"".join(controls)}" fill="none" stroke="{TXT}" stroke-width="1.3" stroke-linecap="round"/>')
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


# full-color official logos; dark parts swapped for their light-background variant
COLOR_FIX = {
    "bash": {"#293138": "#d1d7e0"},
    "kimi": {"currentColor": HI},
    "mysql": {"#00618A": "#5FB0D6"},
}


# official logos that only exist as raster images: (file, image size, viewBox crop)
IMAGES = {
    "nmap": ("nmap.png", 256, "0 34 256 96"),  # the Nmap eye, without the wordmark
    "sqlmap": ("sqlmap.png", 180, "0 0 180 180"),
    "termux": ("termux.png", 192, "0 0 192 192"),
}


def icon(name, x, y, size=20):
    if name in IMAGES:
        file, px, crop = IMAGES[name]
        data = base64.b64encode((ICONS / "img" / file).read_bytes()).decode()
        # box matches the crop's aspect ratio, so nothing outside the crop can show
        cx_, cy_, cw_, ch_ = map(float, crop.split())
        bw = size + 6 if ch_ < cw_ else size
        bh = bw * ch_ / cw_
        return (f'<svg x="{x - 3}" y="{y + (size - bh) / 2:.1f}" width="{bw}" height="{bh:.1f}" viewBox="{crop}">'
                f'<image href="data:image/png;base64,{data}" width="{px}" height="{px}"/></svg>')
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
    h = TOP + 260
    b = frame(h)
    b += prompt(x, TOP, 0.2, [("figlet", "g"), (" levi ", "t"), ("|", "t"), (" lolcat", "g")], 0.6, 1.2, "a")
    # lolcat: hue drifts along a diagonal; blocks drawn as rects since box glyphs render unevenly
    cx, cy, top = 12, 17, TOP + 24
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
    b += prompt(x, TOP + 150, 2.5, [("whoami", "g")], 2.8, 0.5, "b")
    b.append(text(x, TOP + 180, [("Levi", "h b"), (". Full-stack developer with a curious mind. I build, break, debug, and learn.", "t")],
                  cls="a", style=appear(3.45, 0.01)))
    b.append(text(x, TOP + 202, [("Every mistake teaches me something, and every project gives me a reason to keep exploring.", "d")],
                  cls="a", style=appear(3.55, 0.01)))
    b += prompt(x, TOP + 234, 3.8)
    b.append(f'<rect x="{x + PROMPT_LEN * cw(14):.1f}" y="{TOP + 234 - 12}" width="{cw(14):.1f}" height="16" fill="{TXT}" '
             f'opacity="0" style="animation:blink 1.1s steps(1) 3.9s infinite"/>')
    return svg(h, b, "Terminal: figlet levi piped to lolcat, whoami. Levi. Full-stack developer with a curious mind. I build, break, debug, and learn. Every mistake teaches me something, and every project gives me a reason to keep exploring.")


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
    tux_colors = {"K": "#3d444d", "E": HI, "P": BG, "W": HI, "Y": YEL}
    # only the headline items; the full list lives in the stack panel
    rows = [
        ("Role", "full-stack developer"),
        ("OS", "Kali Linux, Windows"),
        ("Web", "HTML, CSS, JavaScript, PHP, Python"),
        ("App", "Java, Kotlin, Dart, C#"),
        ("Frameworks", "React, Tailwind CSS, Laravel, Django, Flask"),
        ("Android", "Android apps, AOSP, Magisk"),
        ("IoT", "ESP32, Arduino, Raspberry Pi"),
        ("Security", "Burp Suite, Metasploit, Nmap"),
        ("Certs", "Cisco Ethical Hacker, Endpoint Security"),
        ("Level", "always learning"),
    ]
    y0 = TOP + 34 + 44  # output starts under the prompt; header and rule take two lines
    h = y0 + len(rows) * 24 + 40
    b = frame(h)
    b += prompt(24, TOP, 0.1, [("neofetch", "g")], 0.3, 0.5, "n")
    px = 9
    # centered on the output block, from the user@host line down to the color bar
    tx, ty = 46, y0 + (len(rows) * 24 - 48) / 2 - len(tux) * px / 2
    cells = "".join(f'<rect x="{tx + c * px}" y="{ty + r * px:.1f}" width="{px}" height="{px}" fill="{tux_colors[ch]}"/>'
                    for r, row in enumerate(tux) for c, ch in enumerate(row) if ch in tux_colors)
    b.append(f'<g class="a" shape-rendering="crispEdges" style="{appear(0.95, 0.05)}">{cells}</g>')
    ix, vx = 270, 270 + 12 * cw(14)
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


# ---------------------------------------------------------------- stack
def stack():
    web_lang = ("web-lang/", [("html5", "HTML"), ("css3", "CSS"), ("javascript", "JavaScript"), ("php", "PHP"),
                              ("python", "Python")])
    app_lang = ("app-lang/", [("java", "Java"), ("kotlin", "Kotlin"), ("dart", "Dart"), ("csharp", "C#")])
    scripting = ("scripting/", [("bash", "Bash"), ("powershell", "PowerShell")])
    frameworks = ("frameworks/", [("react", "React"), ("tailwindcss", "Tailwind CSS"), ("laravel", "Laravel"),
                                  ("django", "Django"), ("flask", "Flask")])
    # Backend-as-a-Service and hosting, named for what they are
    baas = ("baas/", [("firebase", "Firebase"), ("supabase", "Supabase")])
    hosting = ("hosting/", [("vercel", "Vercel")])
    android = ("android/", [("android", "Android apps"), ("android", "AOSP"), ("lineageos", "Custom ROMs"),
                            ("magisk", "Magisk modules"), ("termux", "Termux")])
    iot = ("iot/", [("espressif", "ESP32"), ("espressif", "ESP8266"), ("arduino", "Arduino"),
                              ("raspberrypi", "Raspberry Pi"), ("mqtt", "MQTT")])
    mlcv = ("ml-cv/", [("opencv", "OpenCV"), ("mediapipe", "MediaPipe"), ("numpy", "NumPy")])
    security = ("security/", [("burpsuite", "Burp Suite"), ("metasploit", "Metasploit"), ("sqlmap", "sqlmap"),
                              ("nmap", "Nmap"), ("wireshark", "Wireshark")])
    os_ = ("os/", [("kalilinux", "Kali Linux"), ("archlinux", "BlackArch"), ("parrotsecurity", "Parrot OS"),
                   ("windows11", "Windows"), ("windows11", "Windows Server")])
    ai = ("ai/", [("claude", "Claude"), ("openai", "Codex"), ("nousresearch", "Hermes"), ("kimi", "Kimi")])
    tools = ("tools/", [("vscode", "Visual Studio Code"), ("visualstudio", "Visual Studio"),
                        ("androidstudio", "Android Studio"), ("platformio", "PlatformIO"), ("figma", "Figma"),
                        ("cisco", "Cisco Packet Tracer")])
    database = ("database/", [("mysql", "MySQL"), ("microsoftsqlserver", "SQL Server"), ("oracle", "Oracle"),
                              ("sqlite", "SQLite"), ("mongodb", "MongoDB")])
    # a row is either three small directories side by side, or one wide directory whose items flow across three columns
    layout = [[web_lang, app_lang, scripting], [frameworks], [database, baas, hosting], [android, iot, mlcv], [security],
              [os_, ai, tools]]
    colw, rowh, top = 264, 34, TOP + 20

    def row_height(row):
        n = max(len(items) for _, items in row) if len(row) == 3 else -(-len(row[0][1]) // 3)
        return 26 + n * rowh + 22

    h = top + sum(map(row_height, layout)) - 10
    b = frame(h)
    b += prompt(24, TOP, 0.1, [("ls", "g"), (" ~/stack", "t")], 0.3, 0.5, "s")
    y0 = top
    for row in layout:
        for c, (label, items) in enumerate(row):
            b.append(text(24 + c * colw, y0 + 14, [(label, "bl b")]))  # ls colors directories bold blue
            for i, (ic, name) in enumerate(items):
                # side-by-side directories stack their items; a wide one wraps them across the columns
                col, line = (c, i) if len(row) == 3 else (i % 3, i // 3)
                x, iy = 24 + col * colw, y0 + 30 + line * rowh
                b.append(icon(ic, x, iy))
                b.append(text(x + 30, iy + 14, name))
        y0 += row_height(row)
    return svg(h, b, "Stack. " + " ".join(f"{label.rstrip('/')}: {', '.join(n for _, n in items)}."
                                         for row in layout for label, items in row))


# ---------------------------------------------------------------- log
def log():
    done = [
        "iCuCrops: IoT greenhouse system with ESP32, MQTT, Flask and Supabase",
        "SmartDuck: IoT duck-egg incubator with ESP32, PHP and Supabase",
        "ESP32-CAM streaming live video into a machine learning model",
        "hand and face tracking with MediaPipe + OpenCV",
        "wrote my own Magisk modules",
        "rooted phones, flashed custom ROMs, dug through AOSP",
        "security labs with Nmap, Burp Suite, sqlmap and Metasploit (own gear only)",
        "Cisco Ethical Hacker and Endpoint Security certificates",
        "PC and phone troubleshooting and repair",
    ]
    doing = [
        "building AOSP from source",
    ]
    start = TOP + 34
    h = start - 10 + len(done) * 26 + 18 + len(doing) * 26 + 10
    b = frame(h)
    b += prompt(24, TOP, 0.1, [("cat", "g"), (" ~/notes/now.log", "t")], 0.3, 0.7, "l")
    y, t = start, 1.1
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
    return svg(h, b, "now.log. Done: " + "; ".join(done) + ". In progress: " + "; ".join(doing) + ".")


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
    start = TOP + 34
    top = start + len(rows) * 26 + 6
    h = round(top + 7 * step + 42)
    b = frame(h)
    b += prompt(24, TOP, 0.1, [("gh", "g"), (f" stats {USER}", "t")], 0.3, 0.6, "g")
    vx, nx = 24 + 17 * cw(14), 24 + 30 * cw(14)
    for i, (k, v, note) in enumerate(rows):
        y, st = start + i * 26, appear(1.0 + i * 0.12, 0.01)
        b.append(text(24, y, [(k, "bl b")], cls="a", style=st))
        b.append(text(vx, y, [(v, "h b")], cls="a", style=st))
        b.append(text(nx, y, [(note, "d")], cls="a", style=st))
    # GitHub's dark-mode contribution greens
    levels = ["#2d333b", "#0e4429", "#006d32", "#26a641", "#39d353"]
    peak = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=0) or 1

    def shade(n):
        return levels[0] if n == 0 else levels[min(4, 1 + 4 * (n - 1) // peak)]

    x0 = 24
    t0 = 1.0 + len(rows) * 0.12
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
    # the README alt text repeats the panel's own label, so the two never drift apart
    label = re.search(r'aria-label="([^"]*)"', content).group(1)
    readme = re.sub(rf'(<img src="\./assets/{name}-{ver}\.svg"[^>]*? alt=")[^"]*"', lambda m: m.group(1) + label + '"', readme)
    print("wrote", name, ver)
README.write_text(readme, encoding="utf-8", newline="\n")
