# YT Music Downloader

YouTube 링크를 붙여넣으면 MP3로 다운로드해주는 macOS TUI 앱

![platform](https://img.shields.io/badge/platform-macOS%20Apple%20Silicon-black)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

---

## 스크린샷

```
♪  YT Music Downloader

  음질 선택
    [ 1 ]  최고 품질  (VBR Best ≈ 320kbps)  ← 추천
    [ 2 ]  고음질    (320 kbps)
    [ 3 ]  표준      (192 kbps)
    [ 4 ]  절약      (128 kbps)

  번호 입력 (기본값 1, Enter) :
```

---

## 요구사항

- macOS (Apple Silicon — M1/M2/M3/M4)
- [Homebrew](https://brew.sh)
- `ffmpeg`

```bash
brew install ffmpeg
```

---

## 설치 및 실행

### 바이너리로 실행 (권장)

```bash
# 1. 실행 권한 부여 (최초 1회)
chmod +x yt-music

# 2. 실행
./yt-music
```

> **보안 경고가 뜨는 경우**  
> System Settings → Privacy & Security → "어쨌든 열기" 클릭

### 소스코드로 실행

```bash
# 의존성 설치
pip install yt-dlp rich

# 실행
python3 app.py
```

---

## 사용법

1. 실행 후 음질 선택 (1~4, 기본값 1)
2. YouTube URL 붙여넣기 → Enter
3. 다운로드 완료 시 자동 알림
4. 새 URL 붙여넣기 또는 빈 Enter로 화면 새로고침
5. 종료: `Ctrl+C`

### 지원하는 URL 형식

| 형식 | 저장 위치 |
|------|-----------|
| 단일 영상 | `~/Documents/MugicDownload/` |
| 재생목록 / 앨범 | `~/Documents/MugicDownload/{재생목록명}/` |

---

## 빌드 (개발자용)

```bash
# PyInstaller 바이너리 빌드
./build_app.sh
```

빌드 결과물:
- `dist/yt-music` — 단독 실행 바이너리
- `~/Desktop/YT Music Downloader.app` — 더블클릭 실행 앱

---

## 기술 스택

- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) — YouTube 다운로드
- [`rich`](https://github.com/Textualize/rich) — TUI 렌더링
- `ffmpeg` — MP3 변환
- PyInstaller — 단독 실행 바이너리 패키징
