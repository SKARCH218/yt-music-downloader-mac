#!/usr/bin/env python3
"""YT Music Downloader — Rich TUI"""

import subprocess
import threading
import json
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from rich.cells import cell_len
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.align import Align

# ────────────────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────────────────
DOWNLOAD_DIR = Path.home() / "Documents" / "MugicDownload"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

console = Console()

QUALITIES: dict[str, tuple[str, str]] = {
    "1": ("최고 품질  (VBR Best ≈ 320kbps)", "0"),
    "2": ("고음질    (320 kbps)",             "320K"),
    "3": ("표준      (192 kbps)",             "192K"),
    "4": ("절약      (128 kbps)",             "128K"),
}


# ────────────────────────────────────────────────────────────
# 데이터 모델
# ────────────────────────────────────────────────────────────
class Status(Enum):
    PENDING     = "pending"
    FETCHING    = "fetching"
    DOWNLOADING = "downloading"
    CONVERTING  = "converting"
    DONE        = "done"
    ERROR       = "error"


ACTIVE_STATUSES = {Status.FETCHING, Status.DOWNLOADING, Status.CONVERTING}


@dataclass
class DownloadItem:
    url:           str
    quality_arg:   str
    title:         str    = "불러오는 중…"
    status:        Status = Status.PENDING
    progress:      float  = 0.0
    speed:         str    = ""
    error:         str    = ""
    is_playlist:   bool   = False
    total_tracks:  int    = 0
    done_tracks:   int    = 0
    convert_start: float  = 0.0           # MP3 변환 시작 시각 (time.time())
    added_at: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


downloads: list[DownloadItem] = []
lock = threading.Lock()

BAR_W       = 20
RE_PROGRESS = re.compile(r"\[download\]\s+([\d.]+)%.*?at\s+(\S+)\s+ETA\s+(\S+)")
RE_ITEM     = re.compile(r"\[download\] Downloading item (\d+) of (\d+)")
RE_CONVERT  = re.compile(r"\[ExtractAudio\]|\[ffmpeg\]")


# ────────────────────────────────────────────────────────────
# 진행 바
# ────────────────────────────────────────────────────────────
def make_bar(pct: float, color: str = "cyan") -> Text:
    """일반 채움 바."""
    n = max(0, min(BAR_W, round(pct / 100 * BAR_W)))
    return Text("█" * n + "░" * (BAR_W - n), style=color)


def make_sweep_bar(elapsed: float) -> Text:
    """MP3 변환용 보라색 나이트라이더 스윕 바."""
    block  = max(4, BAR_W // 4)
    period = 1.4                          # 왕복 주기 (초)
    t = (elapsed % period) / period       # 0 ~ 1
    frac = t * 2 if t <= 0.5 else (1.0 - t) * 2
    pos  = int(frac * (BAR_W - block))
    bar  = "░" * pos + "█" * block + "░" * (BAR_W - block - pos)
    return Text(bar, style="bold magenta")


# ────────────────────────────────────────────────────────────
# 테이블
# ────────────────────────────────────────────────────────────
def build_table() -> Table:
    t = Table(
        box=box.SIMPLE_HEAVY,
        expand=True,
        show_header=True,
        header_style="bold bright_white",
        border_style="grey42",
        padding=(0, 1),
    )
    t.add_column("시각",  width=8,  style="dim")
    t.add_column("제목",  ratio=4,  no_wrap=True)
    t.add_column("종류",  width=7,  justify="center")
    t.add_column("상태",  width=15)
    t.add_column("진행",  ratio=3)
    t.add_column("속도",  width=12, justify="right", style="dim")

    COLOR = {
        Status.PENDING:     "dim",
        Status.FETCHING:    "yellow",
        Status.DOWNLOADING: "cyan",
        Status.CONVERTING:  "bold magenta",
        Status.DONE:        "bold green",
        Status.ERROR:       "bold red",
    }

    with lock:
        rows = list(reversed(downloads))

    now = time.time()

    for item in rows:
        c    = COLOR[item.status]
        kind = Text("목록", style="blue") if item.is_playlist else Text("단일", style="cyan")

        # ── 상태 라벨 ──────────────────────────────────────
        if item.status == Status.PENDING:
            label = "대기중"
        elif item.status == Status.FETCHING:
            label = "정보 수집중"
        elif item.status == Status.DOWNLOADING:
            label = (f"{item.done_tracks}/{item.total_tracks} 곡"
                     if item.is_playlist else f"{item.progress:.1f}%")
        elif item.status == Status.CONVERTING:
            label = "MP3 변환중"
        elif item.status == Status.DONE:
            label = f"완료 ({item.total_tracks}곡)" if item.is_playlist else "완료"
        elif item.status == Status.ERROR:
            label = "오류"
        else:
            label = ""

        # ── 진행 바 ────────────────────────────────────────
        if item.status == Status.DOWNLOADING:
            pct = (item.done_tracks / max(item.total_tracks, 1) * 100
                   if item.is_playlist else item.progress)
            bar = make_bar(pct)
            bar.append(f"  {pct:5.1f}%", style="dim")
        elif item.status == Status.CONVERTING:
            elapsed = now - item.convert_start if item.convert_start else 0.0
            bar = make_sweep_bar(elapsed)
            bar.append("  변환중…", style="magenta dim")
        elif item.status == Status.DONE:
            bar = make_bar(100.0, "green")
            bar.append("  100.0%", style="dim green")
        elif item.status == Status.FETCHING:
            bar = Text("⠿  메타데이터 수집중…", style="yellow dim")
        elif item.status == Status.ERROR:
            bar = Text(item.error[:42], style="red")
        else:
            bar = Text("")

        speed = item.speed if item.status == Status.DOWNLOADING else ""
        title = item.title[:54] + "…" if len(item.title) > 54 else item.title

        t.add_row(item.added_at, title, kind, Text(label, style=c), bar, speed)

    return t


# ────────────────────────────────────────────────────────────
# 패널 빌더
# ────────────────────────────────────────────────────────────
def build_panel(quality_label: str, mode: str = "queue") -> Panel:
    """매 호출마다 새 Panel 을 생성해 반환한다.

    mode='queue'       : Queue 모드 힌트
    mode='downloading' : Download 모드 힌트
    """
    with lock:
        done    = sum(1 for d in downloads if d.status == Status.DONE)
        active  = sum(1 for d in downloads if d.status in ACTIVE_STATUSES)
        pending = sum(1 for d in downloads if d.status == Status.PENDING)
        errors  = sum(1 for d in downloads if d.status == Status.ERROR)

    if mode == "downloading":
        hint = Text(
            "  ⏳  다운로드 중…  완료되면 자동으로 입력창이 열립니다",
            style="bold yellow",
        )
    else:
        hint = Text(
            "  URL+Enter 추가   │   /start 시작   │   /mod 음질   │   Ctrl+C 종료",
            style="dim",
        )

    return Panel(
        Group(
            Align.center(Text("♪  YT Music Downloader", style="bold white on dark_red")),
            Text(""),
            Text(f"  음질: {quality_label}   저장: {DOWNLOAD_DIR}", style="dim"),
            Text(""),
            build_table(),
            Text(""),
            Text(
                f"  완료: {done}   진행중: {active}   대기: {pending}   오류: {errors}",
                style="dim",
            ),
            Text(""),
            hint,
        ),
        border_style="dark_red",
        padding=(0, 1),
    )


# ────────────────────────────────────────────────────────────
# URL 입력 박스
# ────────────────────────────────────────────────────────────
def print_url_box() -> None:
    """완전한 URL 입력 박스를 한 번에 그리고 커서를 입력 줄 안으로 이동시킨다."""
    w     = max(50, console.width - 1)   # 터미널 너비 - 1 (줄바꿈 방지)
    inner = w - 2                        # 좌우 │ 사이 실제 너비

    Y = "\033[1;33m"   # 굵은 노란색
    D = "\033[2m"      # 흐린 색
    R = "\033[0m"      # 리셋

    # 상단 테두리: 접두어 표시 너비를 cell_len 으로 계산
    top_prefix  = "╭─ 🎵  YouTube URL 붙여넣기 "
    top_dashes  = max(1, w - cell_len(top_prefix) - 1)   # 1 = ╮
    top_line    = top_prefix + "─" * top_dashes + "╮"

    # 힌트 줄: 한글 2바이트를 cell_len 으로 처리해 패딩 계산
    hint     = "  URL+Enter 추가   │   /start 시작   │   /mod 음질   │   Ctrl+C 종료"
    hint_pad = max(0, inner - cell_len(hint) - 1)   # 1 = 우측 여백

    # ── 5줄 박스 ────────────────────────────────────────────
    #  [0] 상단 테두리
    #  [1] 힌트 줄   (│ 노란색 / 내용 흐림)
    #  [2] 빈 줄
    #  [3] 입력 줄   ← 커서 목표
    #  [4] 하단 테두리
    sys.stdout.write("\n")
    sys.stdout.write(f"{Y}{top_line}{R}\n")
    sys.stdout.write(f"{Y}│{R}{D}{hint}{' ' * hint_pad} {R}{Y}│{R}\n")
    sys.stdout.write(f"{Y}│{' ' * inner}│{R}\n")
    sys.stdout.write(f"{Y}│  >  {' ' * (inner - 5)}│{R}\n")
    sys.stdout.write(f"{Y}╰{'─' * inner}╯{R}\n")

    # 커서를 [3] 입력 줄 "│  >  " 직후로 이동
    # 5줄 + \n 후 커서는 줄 6 맨 앞 → 위로 2줄, 7번 열(1-indexed)
    sys.stdout.write("\033[2A\033[7G")
    sys.stdout.flush()


# ────────────────────────────────────────────────────────────
# 화면 그리기 (Queue 모드용)
# ────────────────────────────────────────────────────────────
def print_screen(quality_label: str) -> None:
    """상태 패널을 출력한다 (화면 지우기 포함)."""
    console.clear()
    console.print(build_panel(quality_label, mode="queue"))


# ────────────────────────────────────────────────────────────
# 다운로드 로직
# ────────────────────────────────────────────────────────────
def run_download(item: DownloadItem) -> None:
    try:
        with lock:
            item.status = Status.FETCHING

        result = subprocess.run(
            ["yt-dlp", "--dump-single-json", "--flat-playlist",
             "--no-warnings", item.url],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            with lock:
                item.status = Status.ERROR
                item.error  = "URL을 불러올 수 없음"
            return

        try:
            info = json.loads(result.stdout)
        except json.JSONDecodeError:
            with lock:
                item.status = Status.ERROR
                item.error  = "메타데이터 파싱 실패"
            return

        is_pl = info.get("_type") == "playlist"
        with lock:
            item.is_playlist = is_pl
            item.title = (
                info.get("title") or info.get("id") or item.url
                if is_pl else info.get("title", item.url)
            )
            if is_pl:
                item.total_tracks = len(info.get("entries") or []) or 1
            item.status = Status.DOWNLOADING

        out_tmpl = (
            str(DOWNLOAD_DIR / "%(playlist_title)s" /
                "%(playlist_index)02d - %(title)s.%(ext)s")
            if is_pl else
            str(DOWNLOAD_DIR / "%(title)s.%(ext)s")
        )

        proc = subprocess.Popen(
            ["yt-dlp", "-x",
             "--audio-format",  "mp3",
             "--audio-quality", item.quality_arg,
             "--embed-thumbnail", "--add-metadata",
             "--newline", "--no-warnings",
             "-o", out_tmpl, item.url],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )

        for raw in proc.stdout:
            line = raw.rstrip()
            with lock:
                m = RE_ITEM.search(line)
                if m:
                    item.done_tracks  = int(m.group(1))
                    item.total_tracks = int(m.group(2))
                m2 = RE_PROGRESS.search(line)
                if m2:
                    item.progress = float(m2.group(1))
                    item.speed    = m2.group(2)
                if RE_CONVERT.search(line) and item.status != Status.CONVERTING:
                    item.status        = Status.CONVERTING
                    item.convert_start = time.time()
                    item.speed         = ""

        proc.wait()
        with lock:
            if proc.returncode == 0:
                item.status   = Status.DONE
                item.progress = 100.0
                item.speed    = ""
                if is_pl:
                    item.done_tracks = item.total_tracks
            else:
                item.status = Status.ERROR
                item.error  = f"다운로드 실패 (exit {proc.returncode})"

    except Exception as exc:
        with lock:
            item.status = Status.ERROR
            item.error  = str(exc)[:45]


# ────────────────────────────────────────────────────────────
# 음질 선택
# ────────────────────────────────────────────────────────────
def select_quality() -> tuple[str, str]:
    console.clear()
    console.print(Panel(
        Align.center(Text("♪  YT Music Downloader", style="bold white on dark_red")),
        border_style="dark_red", padding=(1, 4),
    ))
    console.print()
    console.print("  [bold]음질 선택[/bold]\n")
    for key, (label, _) in QUALITIES.items():
        rec = "  [dim]← 추천[/dim]" if key == "1" else ""
        console.print(f"    [bold cyan][ {key} ][/bold cyan]  {label}{rec}")
    console.print()

    while True:
        try:
            ch = console.input(
                "  [bold yellow]번호 입력[/] [dim](기본값 1, Enter)[/] : "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)

        if ch == "":
            ch = "1"
        if ch in QUALITIES:
            label, arg = QUALITIES[ch]
            return label.split("(")[0].strip(), arg
        console.print("  [red]1~4 중 하나를 입력하세요.[/red]")


# ────────────────────────────────────────────────────────────
# Queue 모드
# ────────────────────────────────────────────────────────────
def queue_mode(quality_label: str, quality_arg: str) -> str:
    """URL 입력 루프.

    반환값:
        'start' — PENDING 항목을 다운로드 시작해야 함
        'mod'   — 음질 재선택 요청
        'quit'  — 종료 요청
    """
    while True:
        print_screen(quality_label)
        print_url_box()

        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            return "quit"

        if not line:          # EOF (Ctrl+D)
            return "quit"

        text = line.strip()

        # 빈 Enter → 화면 새로고침만
        if not text:
            continue

        # 커맨드
        if text == "/start":
            with lock:
                has_pending = any(d.status == Status.PENDING for d in downloads)
            if has_pending:
                return "start"
            # PENDING 없으면 무시
            continue

        if text == "/mod":
            return "mod"

        # URL 유효성
        if not text.startswith(("http://", "https://")):
            # 유효하지 않은 입력 무시
            continue

        # 중복 체크
        with lock:
            already = any(
                d.url == text for d in downloads
                if d.status not in {Status.DONE, Status.ERROR}
            )
        if already:
            continue

        # PENDING 상태로 목록에 추가 (다운로드 시작 안 함)
        item = DownloadItem(url=text, quality_arg=quality_arg)
        with lock:
            downloads.append(item)
        # 화면 새로고침 (continue → 루프 상단으로)
        continue


# ────────────────────────────────────────────────────────────
# Download 모드
# ────────────────────────────────────────────────────────────
def download_mode(quality_label: str, items_to_download: list[DownloadItem]) -> None:
    """PENDING 항목들을 병렬 다운로드하고, 0.25s 주기로 화면 자동 갱신한다."""

    # PENDING 항목마다 스레드 시작
    for item in items_to_download:
        threading.Thread(target=run_download, args=(item,), daemon=True).start()

    # 자동 새로고침 루프 (입력 없음)
    while True:
        console.clear()
        console.print(build_panel(quality_label, mode="downloading"))

        with lock:
            still_active = any(
                d.status in ACTIVE_STATUSES or d.status == Status.PENDING
                for d in items_to_download
            )
        if not still_active:
            break

        time.sleep(0.25)

    # 완료 후 최종 화면 한 번 더
    console.clear()
    console.print(build_panel(quality_label, mode="downloading"))

    # 완료 요약
    with lock:
        done_count  = sum(1 for d in items_to_download if d.status == Status.DONE)
        error_count = sum(1 for d in items_to_download if d.status == Status.ERROR)

    if error_count == 0:
        console.print(f"\n  [bold green]✅  {done_count}개 모두 완료![/bold green]")
    else:
        console.print(
            f"\n  [bold green]✅  완료: {done_count}개[/bold green]"
            f"   [bold red]❌ 오류: {error_count}개[/bold red]"
        )
    time.sleep(1.5)


# ────────────────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────────────────
def main() -> None:
    quality_label, quality_arg = select_quality()

    while True:
        action = queue_mode(quality_label, quality_arg)

        if action == "quit":
            console.print("\n[dim]종료합니다.[/]")
            sys.exit(0)

        if action == "mod":
            quality_label, quality_arg = select_quality()
            with lock:
                for d in downloads:
                    if d.status == Status.PENDING:
                        d.quality_arg = quality_arg
            continue

        if action == "start":
            with lock:
                pending = [d for d in downloads if d.status == Status.PENDING]
            if pending:
                download_mode(quality_label, pending)


if __name__ == "__main__":
    main()
