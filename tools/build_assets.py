"""Generate the terminal-themed SVG assets for the Levi-crown profile README.

usage: python tools/build_assets.py assets   (also updates image links in README.md)
"""
import base64
import colorsys
import hashlib
import re
import sys
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
KALI_TOP = [("┌──(", "g"), ("levi㉿kali", "bl b"), (")-[", "g"), ("~", "h b"), ("]", "g")]


def kali_prompt(x, y, t, cmd=None, type_start=None, type_dur=None, kid=""):
    """Two-line Kali zsh prompt. Optionally types `cmd` (list of parts) with a stepping cover + cursor."""
    out = [text(x, y, KALI_TOP, cls="a", style=appear(t, 0.01)),
           text(x, y + 22, [("└─", "g"), ("$ ", "bl b")], cls="a", style=appear(t, 0.01))]
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
    b.append(text(x, 288, [("Levi", "h b"), (". Python dev who lives in the terminal and takes things apart to see how they work.", "t")],
                  cls="a", style=appear(3.45, 0.01)))
    b.append(text(x, 310, [("Not an expert at any of it. I just keep going until it works.", "d")],
                  cls="a", style=appear(3.55, 0.01)))
    b += kali_prompt(x, 336, 3.8)
    b.append(f'<rect x="{x + 4 * cw(14):.1f}" y="{336 + 22 - 12}" width="{cw(14):.1f}" height="16" fill="{TXT}" '
             f'opacity="0" style="animation:blink 1.1s steps(1) 3.9s infinite"/>')
    return svg(h, b, "Terminal: figlet levi piped to lolcat, whoami. Levi, Python dev who lives in the terminal. Not an expert, keeps going until it works.")


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
        ("OS", "Kali, BlackArch, Parrot OS, Windows, Windows Server"),
        ("Shell", "bash, PowerShell"),
        ("Editor", "Visual Studio Code"),
        ("IDE", "Visual Studio, Android Studio, PlatformIO"),
        ("Language", "Python (main), Java, C#"),
        ("Database", "MySQL, SQL Server, Oracle, SQLite, MongoDB"),
        ("Backend", "Firebase, Supabase"),
        ("AI", "Claude, Codex, Hermes, Kimi"),
        ("ML / CV", "OpenCV, MediaPipe, ML fundamentals"),
        ("Android", "AOSP, rooting, custom ROMs, Magisk modules"),
        ("Embedded", "ESP32, Arduino, Raspberry Pi"),
        ("Network", "Cisco Packet Tracer, Nmap, Wireshark"),
        ("Hardware", "PC and phone troubleshooting / repair"),
        ("Security", "ethical hacking (own gear or with permission)"),
        ("Level", "not an expert, still learning"),
    ]
    h = 524
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
    return svg(h, b, "neofetch: OS Kali Linux, BlackArch, Parrot OS, Windows, Windows Server. Network Cisco Packet Tracer, Nmap, Wireshark. Shell bash, PowerShell. Language Python, Java, C#. Database MySQL, SQL Server, Oracle, SQLite, MongoDB. Backend Firebase, Supabase. Editor Visual Studio Code. IDE Visual Studio, Android Studio, PlatformIO. AI Claude, Codex, Hermes, Kimi. "
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
                     "embedded: ESP32, Arduino, Raspberry Pi. os: Kali Linux, BlackArch, Parrot OS, Windows, Windows Server. network: Cisco Packet Tracer, Nmap, Wireshark. "
                     "android: AOSP, custom ROMs, Magisk modules. "
                     "database: MySQL, Microsoft SQL Server, Oracle, SQLite, MongoDB, Firebase, Supabase. tools: Visual Studio Code, Visual Studio, Android Studio, PlatformIO IDE.")


# ---------------------------------------------------------------- log
def log():
    done = [
        "wrote my own Magisk modules",
        "hand and face tracking with MediaPipe + OpenCV",
        "ESP32 / Arduino / Raspberry Pi builds: sensors, wiring, lots of trial and error",
        "rooted phones, flashed custom ROMs, dug through AOSP",
        "security labs on Kali, BlackArch and Parrot (own gear only)",
        "PC and phone hardware troubleshooting and repair",
    ]
    doing = [
        "going deeper into machine learning",
        "building AOSP from source",
        "getting an ESP32 camera to feed a Python CV script",
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
    return svg(h, b, "Log. Done: Magisk modules, MediaPipe + OpenCV tracking, ESP32/Arduino/Raspberry Pi builds, "
                     "rooting and custom ROMs, security labs, hardware repair. In progress: machine learning, "
                     "building AOSP from source, ESP32 camera to Python CV.")


README = Path(__file__).parent.parent / "README.md"
readme = README.read_text(encoding="utf-8")
for name, fn in [("hero", hero), ("neofetch", neofetch), ("stack", stack), ("log", log)]:
    content = fn()
    # GitHub's /raw/ redirect drops query strings and raw files are cached for 5 min,
    # so the content hash goes in the filename to give every version a fresh URL
    ver = hashlib.sha1(content.encode()).hexdigest()[:8]
    for old in OUT.glob(f"{name}*.svg"):
        old.unlink()
    (OUT / f"{name}-{ver}.svg").write_text(content, encoding="utf-8")
    readme = re.sub(rf"\./assets/{name}(-\w+)?\.svg(\?v=\w+)?", f"./assets/{name}-{ver}.svg", readme)
    print("wrote", name, ver)
README.write_text(readme, encoding="utf-8", newline="\n")
