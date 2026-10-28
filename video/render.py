#!/usr/bin/env python3
"""Rebuild the demo video's visuals around an existing narration track.

The audio is never touched: same voice, same length, same words. What this
controls is everything the viewer looks at -- the beats, the captions, and the
type-on reveal.

Every panel body is output captured from a real run. Nothing is invented for
the screen, and the frame itself says so ("not a live run"), because a security
tool that fakes a terminal is not worth watching.

Usage
-----
    pip install pillow imageio-ffmpeg
    python video/render_video.py --audio narration.mp4 --out demo.mp4

`--audio` can be the original recording (its soundtrack is reused) or any
audio file. `--beats` prints the beat sheet without rendering.

Requires a monospace and a bold sans font; DejaVu ships with most Linux images
and is what the committed copy was rendered with. Point --font-dir elsewhere if
your system differs.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 25
END = 121.9  # seconds; must match the narration track

C = {
    "bg0": (7, 9, 13),
    "bg1": (13, 17, 24),
    "panel": (13, 16, 22),
    "line": (32, 39, 52),
    "fg": (222, 230, 242),
    "dim": (128, 140, 160),
    "green": (61, 220, 151),
    "red": (255, 107, 129),
    "amber": (242, 193, 78),
    "cyan": (99, 201, 245),
    "white": (255, 255, 255),
    "violet": (169, 151, 255),
}

STYLE = {
    "cmd": "cyan",
    "ok": "green",
    "bad": "red",
    "add": "green",
    "del": "red",
    "warn": "amber",
    "dim": "dim",
    "hdr": "white",
    "green": "green",
    "cyan": "cyan",
    "violet": "violet",
    "amber": "amber",
    "red": "red",
    "white": "white",
    "fg": "fg",
}


@dataclass
class Beat:
    """One panel. `start` is when it cuts in, in seconds of the narration."""

    start: float
    label: str
    caption: str
    body: tuple[tuple[str, str], ...]
    kind: str = "panel"  # panel | endcard


B = Beat
BEATS: tuple[Beat, ...] = (
    B(
        0.15,
        "the vulnerable line",
        "That command parameter is controlled by an LLM agent.",
        (
            ("@mcp.tool()", "dim"),
            ("def run(cmd, limit: int = 1000) -> str:", "fg"),
            ("    subprocess.run(cmd, shell=True, check=False)", "bad"),
            ("    os.system(cmd)", "bad"),
            ("    return str(limit)", "fg"),
        ),
    ),
    B(
        4.2,
        "the vulnerable line",
        "One line — shell=True — and the agent can run anything on the machine.",
        (
            ("@mcp.tool()", "dim"),
            ("def run(cmd, limit: int = 1000) -> str:", "fg"),
            ("    subprocess.run(cmd, shell=True, check=False)", "bad"),
            ("    os.system(cmd)", "bad"),
            ("    return str(limit)", "fg"),
            ("", "fg"),
            ("# cmd is whatever the model was told to send", "dim"),
        ),
    ),
    B(
        9.9,
        "why it matters",
        "MCP servers are how AI agents touch the real world.",
        (
            ("$ vexar-mcp scan examples/vulnerable_server.py", "cmd"),
            ("", "fg"),
            ("MCP servers · run commands · fetch URLs", "fg"),
            ("            · read and write files", "fg"),
            ("            · query databases", "fg"),
            ("", "fg"),
            ("on an agent's behalf.", "dim"),
        ),
    ),
    B(
        13.6,
        "why it matters",
        "Almost none of them are audited.",
        (
            ("MCP servers · run commands · fetch URLs", "fg"),
            ("            · read and write files", "fg"),
            ("            · query databases", "fg"),
            ("", "fg"),
            ("audited ............................. ", "dim"),
        ),
    ),
    B(
        16.7,
        "vexar-mcp · real output",
        "A static scanner finds the problems.",
        (
            ("$ vexar-mcp scan examples/vulnerable_server.py", "cmd"),
            ("", "fg"),
            ("Health Score: 4/100 (F)   Risk Index: 98/100 (critical)", "fg"),
            ("", "fg"),
            ("  MCP005  dangerous shell execution          error", "bad"),
            ("  MCP006  SSRF sink, no host allowlist      warning", "bad"),
            ("  MCP007  unconfined filesystem access      warning", "bad"),
            ("  MCP010  outbound HTTP, no timeout         warning", "bad"),
        ),
    ),
    B(
        25.0,
        "vexar-mcp · real output",
        "Finding them was never the hard part.",
        (
            ("Health Score: 4/100 (F)   Risk Index: 98/100 (critical)", "fg"),
            ("", "fg"),
            ("  MCP005  dangerous shell execution", "bad"),
            ("  MCP006  SSRF sink, no host allowlist", "bad"),
            ("  MCP007  unconfined filesystem access", "bad"),
            ("  MCP010  outbound HTTP, no timeout", "bad"),
            ("", "fg"),
            ("  ... and 5 rules with no mechanical remedy", "dim"),
        ),
    ),
    B(
        28.3,
        "the obvious next step",
        "So you point an LLM at the file.",
        (
            ("$ fix_this_file examples/vulnerable_server.py", "cmd"),
            ("", "fg"),
            ("  diff written .......... 12 lines", "fg"),
            ('  model says ............ "fixed"', "amber"),
        ),
    ),
    B(
        31.6,
        "the obvious next step",
        "Now you have a diff from a model that will tell you confidently that it worked.",
        (
            ('  model says ............ "fixed"  ← it always says this', "amber"),
            ("  scanner reruns ........ rule gone", "fg"),
            ("", "fg"),
            ("and no way to check the thing you actually care about:", "dim"),
            ("does the tool still work?", "white"),
        ),
    ),
    B(
        38.0,
        "the design decision",
        "I didn't want to build that. So I built the verifier first, and the agent second.",
        (
            ("verifier  ->  decides", "green"),
            ("agent     ->  proposes", "dim"),
            ("", "fg"),
            ("a model opinion is never the last word", "white"),
        ),
    ),
    B(
        41.5,
        "first live run · recorded",
        "Nemotron-3 Nano triages every finding.",
        (
            ("$ vexar-autofix --target examples/vulnerable_server.py", "cmd"),
            ("", "fg"),
            ("scanning    12 findings", "fg"),
            ("triaging    nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "cyan"),
            ("            4 queued  · 7 refused  · 1 skipped", "fg"),
        ),
    ),
    B(
        46.0,
        "first live run · recorded",
        "Super writes the patches, and the scanner reruns.",
        (
            ("triaging    nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "cyan"),
            ("patching    nvidia/nemotron-3-super-120b-a12b", "green"),
            ("verifying   rescan + patch audit", "fg"),
            ("", "fg"),
            ("  MCP005  accepted", "green"),
            ("  MCP006  accepted", "green"),
            ("  MCP007  accepted", "green"),
            ("  MCP010  accepted", "green"),
        ),
    ),
    B(
        50.5,
        "first live run · recorded",
        "Four patches are accepted. Score: 4 to 46.",
        (
            ("", "fg"),
            ("  before     4/100   (F)", "red"),
            ("  after     46/100   (F)", "amber"),
            ("", "fg"),
            ("4 verified · 0 regressions · 18 model calls", "green"),
        ),
    ),
    B(
        54.1,
        "then I read the diff",
        "The shell fix flipped shell=False, but still passed the command as one string.",
        (
            ("--- a/vulnerable_server.py", "dim"),
            ("+++ b/vulnerable_server.py", "dim"),
            ("- subprocess.run(cmd, shell=True, check=False)", "del"),
            ("- os.system(cmd)", "del"),
            ("+ subprocess.run(cmd, shell=False, check=False)", "add"),
            ("", "fg"),
            ("the scanner was satisfied", "dim"),
        ),
    ),
    B(
        59.5,
        "then I ran it",
        "I ran it. FileNotFoundError.",
        (
            (">>> subprocess.run('git status --short', shell=False)", "cmd"),
            ("", "fg"),
            ("FileNotFoundError: [Errno 2] No such file or directory:", "red"),
            ("  'git status --short'", "red"),
            ("", "fg"),
            ("subprocess went looking for a file with that literal name", "dim"),
        ),
    ),
    B(
        66.5,
        "then I ran it",
        "The tool was broken by its own fix — and the scanner was happy, because the rule was gone.",
        (
            ("FileNotFoundError: 'git status --short'", "red"),
            ("", "fg"),
            ("  scanner verdict ....... MCP005 cleared", "green"),
            ("  can the tool run? ..... no", "red"),
        ),
    ),
    B(
        72.5,
        "the insight",
        "Clearing a rule is not the same as fixing the code.",
        (("a rule cleared      !=  code that works", "white"),),
    ),
    B(
        76.8,
        "the third stage",
        "So the verifier gained a third stage: a deterministic audit of only the lines the patch added.",
        (
            ("1  rescan      targeted count must drop", "fg"),
            ("2  audit       does the patch implement the remedy?", "green"),
            ("3  tests       does the suite still pass?", "fg"),
            ("", "fg"),
            ("reads added lines only — existing code can't trigger it", "dim"),
        ),
    ),
    B(
        81.4,
        "the third stage",
        "shell=False on a string, an SSRF fix with no host allowlist, path confinement by string prefix.",
        (
            ("MCP005 rejected", "red"),
            ("  shell=False while still passing the command as one string", "dim"),
            ("MCP006 rejected", "red"),
            ("  no host allowlist found; the scheme check prevents nothing", "dim"),
            ("MCP007 rejected", "red"),
            ("  confines by string prefix — '<base>-evil' passes '<base>'", "dim"),
        ),
    ),
    B(
        89.0,
        "the third stage",
        "Each one rejected, with the reason fed back to the model.",
        (
            ("MCP005 rejected  →  reason", "red"),
            ("MCP006 rejected  →  reason", "red"),
            ("MCP007 rejected  →  reason", "red"),
            ("", "fg"),
            ("escalate: nemotron-3-ultra receives the failure text", "violet"),
        ),
    ),
    B(
        92.7,
        "second run",
        "Same file, second run — the canonical remedies.",
        (
            ("- subprocess.run(cmd, shell=True, check=False)", "del"),
            ("- os.system(cmd)", "del"),
            ("+ subprocess.run(shlex.split(cmd), check=False)", "add"),
            ("", "fg"),
            ("+ if urlsplit(url).hostname not in ALLOWED_HOSTS: raise", "add"),
            ("+ resolved = Path(p).resolve()", "add"),
            ("+ if not resolved.is_relative_to(BASE_DIR): raise", "add"),
            ("+ urlopen(url, timeout=10)", "add"),
        ),
    ),
    B(
        96.1,
        "the hard fixture",
        "And on the hard fixture — sinks hidden one level deep inside helper functions.",
        (
            ("def _run_cmd(cmd):", "fg"),
            ("    return subprocess.run(cmd, shell=True).returncode", "bad"),
            ("", "fg"),
            ("@mcp.tool()", "dim"),
            ("def run_backup(command: str) -> str:", "fg"),
            ("    return f'exit={_run_cmd(command)}'", "fg"),
            ("", "fg"),
            ("the tool body looks clean", "dim"),
        ),
    ),
    B(
        101.6,
        "the hard fixture",
        "All three fixed. 73 to 100. Zero regressions.",
        (
            ("  helper_delegation_server.py", "fg"),
            ("  before    73/100   (C)", "amber"),
            ("  after    100/100   (A+)", "green"),
            ("", "fg"),
            ("3 verified · 0 refused · 0 regressions", "green"),
        ),
    ),
    B(
        106.1,
        "provenance",
        "Two cents of inference. Token Factory served every call.",
        (
            ("provider   Nebius Token Factory", "fg"),
            ("triage     nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "cyan"),
            ("patch      nvidia/nemotron-3-super-120b-a12b", "green"),
            ("escalate   nvidia/Nemotron-3-Ultra-550b-a55b", "violet"),
            ("", "fg"),
            ("18 calls · $0.0226 total", "white"),
        ),
    ),
    B(
        109.0,
        "provenance",
        "Nano to triage, Super to patch, Ultra only after a verified failure.",
        (
            ("triage    Nano 30B A3B     $0.06 / $0.24 per 1M   every finding", "cyan"),
            ("patch     Super 120B A12B  $0.30 / $0.90 per 1M   per queue entry", "green"),
            ("escalate  Ultra 550B A55B  $1.00 / $3.00 per 1M   only on failure", "violet"),
            ("", "fg"),
            ("routing signal = verified failure, not guessed difficulty", "dim"),
        ),
    ),
    B(
        114.0,
        "the design",
        "The scanner sits on both sides of the agent.",
        (
            ("find  →  model proposes  →  verify", "fg"),
            ("  ^                          |", "dim"),
            ("  +--------------------------+", "dim"),
            ("     same scanner, both ends", "green"),
        ),
    ),
    B(
        119.0,
        "vexar-autofix",
        "An MCP security agent that can prove it fixed your code.",
        (
            ("github.com/RANJITHROSAN17/vexar-autofix", "green"),
            ("RANJITHROSAN17.github.io/vexar-autofix", "green"),
        ),
        kind="endcard",
    ),
)


class Fonts:
    """Font set, resolved from a directory so the renderer is portable."""

    def __init__(self, font_dir: Path) -> None:
        self.hdr = ImageFont.truetype(str(font_dir / "DejaVuSansMono-Bold.ttf"), 22)
        self.body = ImageFont.truetype(str(font_dir / "DejaVuSansMono.ttf"), 31)
        self.body_b = ImageFont.truetype(str(font_dir / "DejaVuSansMono-Bold.ttf"), 31)
        self.cap = ImageFont.truetype(str(font_dir / "DejaVuSans-Bold.ttf"), 36)
        self.meta = ImageFont.truetype(str(font_dir / "DejaVuSansMono.ttf"), 18)
        self.big = ImageFont.truetype(str(font_dir / "DejaVuSans-Bold.ttf"), 78)
        self.big2 = ImageFont.truetype(str(font_dir / "DejaVuSans-Bold.ttf"), 44)


def gradient() -> Image.Image:
    img = Image.new("RGB", (W, H), C["bg0"])
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line(
            [(0, y), (W, y)],
            fill=tuple(int(C["bg0"][i] + (C["bg1"][i] - C["bg0"][i]) * t) for i in range(3)),
        )
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(700, 0, -28):
        a = int(16 * (1 - r / 700))
        gd.ellipse([260 - r, -260 - r + 220, 260 + r, 260 + r - 180], fill=(a, a * 2, a))
    return Image.blend(img, Image.composite(glow, img, glow.convert("L")), 0.55)


def wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for word in text.split():
        candidate = (cur + " " + word).strip()
        if font.getlength(candidate) <= max_w:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_body_line(
    d: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    style: str,
    fonts: Fonts,
    alpha: float = 1.0,
) -> None:
    if alpha <= 0.02:
        return
    color = C[STYLE[style]]
    font = fonts.body_b if style in ("cmd", "white", "hdr") else fonts.body
    if style in ("add", "del"):
        tint = (61, 220, 151, 26) if style == "add" else (255, 107, 129, 26)
        edge = C["green"] if style == "add" else C["red"]
        right = x + font.getlength(text) + 14
        d.rectangle([x - 18, y - 6, right, y + 40], fill=(*tint[:3], int(tint[3] * alpha)))
        d.rectangle([x - 18, y - 6, x - 14, y + 40], fill=(*edge, int(190 * alpha)))
    d.text((x, y), text, font=font, fill=(*color, int(255 * alpha)))


def draw_endcard(frame: Image.Image, local: float, fonts: Fonts) -> None:
    d = ImageDraw.Draw(frame, "RGBA")
    a = int(255 * min(1.0, max(0.0, local / 0.45)))
    d.rectangle([0, 0, W, H], fill=(7, 9, 13, a))
    line1 = "An MCP security agent that can"
    line2 = "prove it fixed your code."
    y = 400
    d.text(((W - fonts.big.getlength(line1)) / 2, y), line1, font=fonts.big, fill=(*C["white"], a))
    d.text(((W - fonts.big.getlength(line2)) / 2, y + 96), line2, font=fonts.big, fill=(*C["green"], a))
    d.line([(W / 2 - 120, y + 210), (W / 2 + 120, y + 210)], fill=(*C["line"], a), width=2)
    uy = y + 250
    for url, color in (
        ("github.com/RANJITHROSAN17/vexar-autofix", C["green"]),
        ("RANJITHROSAN17.github.io/vexar-autofix", C["cyan"]),
    ):
        d.text(((W - fonts.big2.getlength(url)) / 2, uy), url, font=fonts.big2, fill=(*color, a))
        uy += 62
    meta = "recorded 2026-10-28 · commit 30313a1 · Nebius Token Factory · NVIDIA Nemotron"
    d.text(((W - fonts.meta.getlength(meta)) / 2, uy + 40), meta, font=fonts.meta, fill=(*C["dim"], a))
    disclosure = "output recorded from the committed run data — not a live screen capture"
    d.text(
        ((W - fonts.meta.getlength(disclosure)) / 2, uy + 74),
        disclosure,
        font=fonts.meta,
        fill=(*C["dim"], a),
    )


def make_frame(t: float, bg: Image.Image, fonts: Fonts) -> Image.Image:
    """Render one frame at `t` seconds."""
    idx = 0
    for i, beat in enumerate(BEATS):
        if t >= beat.start:
            idx = i
    beat = BEATS[idx]
    local = t - beat.start
    frame = bg.copy()
    d = ImageDraw.Draw(frame, "RGBA")

    if beat.kind == "endcard":
        draw_endcard(frame, local, fonts)
        d.rectangle([0, H - 6, W, H], fill=(*C["line"], 255))
        d.rectangle([0, H - 6, int(W * (t / END)), H], fill=(*C["green"], 255))
        return frame

    left, top, right, bottom = 110, 74, W - 110, 812
    d.rounded_rectangle(
        [left, top, right, bottom], 14, fill=(*C["panel"], 255), outline=(*C["line"], 255), width=2
    )
    d.line([(left + 1, top + 64), (right - 1, top + 64)], fill=(*C["line"], 255), width=1)
    d.text((left + 34, top + 21), "vexar-autofix", font=fonts.hdr, fill=C["green"])
    d.text(
        (right - 34 - fonts.hdr.getlength(beat.label), top + 21), beat.label, font=fonts.hdr, fill=C["dim"]
    )

    # Every line lands immediately, staggered by 35 ms: the frame reads as alive
    # without making anyone wait to read it.
    line_h = 47
    body_h = len(beat.body) * line_h
    x = left + 60
    y = top + 108 + max(0, (bottom - top - 96 - body_h) // 2)
    for i, (text, style) in enumerate(beat.body):
        alpha = 1.0
        if local < 0.35:
            alpha = max(0.0, min(1.0, (local - i * 0.035) / 0.22))
        draw_body_line(d, x, y, text, style, fonts, alpha)
        y += line_h

    # Caption, shrunk rather than truncated -- the old cut-off captions were the
    # single worst thing about the first cut.
    cap_font = fonts.cap
    lines = wrap(beat.caption, cap_font, 1560)
    while len(lines) > 2 and cap_font.size > 26:
        cap_font = ImageFont.truetype(cap_font.path, cap_font.size - 3)
        lines = wrap(beat.caption, cap_font, 1560)
    cap_y = 872 - (len(lines) - 1) * 22
    cap_alpha = int(255 * min(1.0, max(0.0, (local - 0.10) / 0.35)))
    for line in lines:
        d.text(
            ((W - cap_font.getlength(line)) / 2, cap_y), line, font=cap_font, fill=(*C["white"], cap_alpha)
        )
        cap_y += cap_font.size + 14

    d.rectangle([0, H - 6, W, H], fill=(*C["line"], 255))
    d.rectangle([0, H - 6, int(W * (t / END)), H], fill=(*C["green"], 255))
    d.text((left + 34, H - 44), f"{idx + 1:02d} / {len(BEATS):02d}", font=fonts.meta, fill=C["dim"])
    # Footer: the provenance stamp is right-aligned, and the honesty label sits to its
    # left at a computed offset -- a fixed x overlapped the stamp once its width grew.
    stamp = "recorded 2026-10-28 · commit 30313a1"
    stamp_x = right - 34 - fonts.meta.getlength(stamp)
    d.text((stamp_x, H - 44), stamp, font=fonts.meta, fill=C["dim"])
    note = "not a live run"
    d.text((stamp_x - 30 - fonts.meta.getlength(note), H - 44), note, font=fonts.meta, fill=C["amber"])
    return frame


def ffmpeg_path() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def render(audio: Path, out: Path, font_dir: Path) -> int:
    fonts = Fonts(font_dir)
    bg = gradient()
    total = int(END * FPS)
    cmd = [
        ffmpeg_path(),
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "pipe:0",
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(total):
            assert proc.stdin is not None
            proc.stdin.write(make_frame(i / FPS, bg, fonts).tobytes())
            if i % 500 == 0:
                print(f"  frame {i}/{total}", flush=True)
    finally:
        if proc.stdin:
            proc.stdin.close()
    rc = proc.wait()
    size = out.stat().st_size / 1e6 if out.exists() else 0
    print(f"ffmpeg exit {rc} -> {out} ({size:.1f} MB, {total / FPS:.0f}s)")
    return rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the demo video visuals.")
    parser.add_argument("--audio", type=Path, help="source file whose audio track is reused")
    parser.add_argument("--out", type=Path, default=Path("video/vexar-autofix-demo.mp4"))
    parser.add_argument("--font-dir", type=Path, default=Path("/usr/share/fonts/truetype/dejavu"))
    parser.add_argument("--beats", action="store_true", help="print the beat sheet and exit")
    args = parser.parse_args(argv)

    if args.beats:
        for i, beat in enumerate(BEATS, 1):
            end = BEATS[i].start if i < len(BEATS) else END
            print(f"{beat.start:7.2f} → {end:7.2f}  {beat.label:28}  {beat.caption}")
        return 0
    if not args.audio:
        parser.error("--audio is required to render (or use --beats)")
    if not args.audio.exists():
        parser.error(f"audio source not found: {args.audio}")
    return render(args.audio, args.out, args.font_dir)


if __name__ == "__main__":
    raise SystemExit(main())
