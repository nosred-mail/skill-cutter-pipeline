#!/usr/bin/env python3
"""Motor unificado e autocontido do Cutter Pipeline (Geracao 1: Lote | Geracao 2: Hibrido Narrativo).

Projetado para ser portavel entre qualquer agente de IA (Antigravity, Claude Code, Codex, Cursor, Windsurf):
- Zero dependencia de caminhos externos ocultos (modelo YuNet, fontes, graficos e SFX embutidos em ../assets).
- Suporta:
  1. `doctor` / `setup`: diagnostico e provisionamento automatico de ambiente Python/CUDA/FFmpeg.
  2. `extract` / `evidence` / `detect-cam`: ingestao de video bruto/URL, transcricao faster-whisper
     (`transcript.json` + `transcript_lines.txt`) e pranchas de frames (`evidence/*.jpg`) para curadoria.
  3. `parse-md`: leitura de arquivos Markdown com timestamps e ganchos (`*destaque*`).
  4. `batch` / `batch-top`: Producao em Lote (Preset Individual com banner 3D enrolando + Preset TOP).
  5. `hybrid`: Padrao Hibrido Narrativo (multi-segmentos, Cold Open, Rewind, Promessa, HUD Callout,
     Joke Dissolve com data-color-grading, BigCam Punch-in, BGM/SFX e Final Abrupto estilo GTA).
  6. `seo-txt`: geracao padronizada do arquivo `.txt` (YouTube Shorts, Instagram Reels MATCH, TikTok).
  7. `self-test`: geracao sintetica dos modos `batch` e `hybrid` para validacao no HyperFrames CLI.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MODELS_DIR = ASSETS_DIR / "models"
GRAPHICS_DIR = ASSETS_DIR / "graphics"
SFX_DIR = ASSETS_DIR / "sfx"

CANVAS_W = 1080
CANVAS_H = 1920
FPS = 30

FORMATO_YTDLP = "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b"
FORMATO_YTDLP_HLS = "bv*[height<=1080][protocol^=m3u8]+ba[protocol^=m3u8]/312+234/312+233/bv*[height<=1080]+ba/b"
FORMATO_AUDIO_YTDLP = "ba[ext=m4a]/ba/b"

LIGHTWEIGHT_CMDS = {"parse-md", "doctor", "setup", "seo-txt"}


# =====================================================================
# 0. Ambiente, Binarios e Descoberta Multi-Plataforma
# =====================================================================
def _candidatos_python() -> list[Path]:
    exe_rel = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    cands = [
        Path.cwd() / ".venv" / exe_rel,
        SKILL_DIR / ".venv" / exe_rel,
        SKILL_DIR.parent.parent.parent / ".venv" / exe_rel,
        Path.home() / "clipper-gta6" / "ambiente" / exe_rel,
    ]
    vistos: set[str] = set()
    out: list[Path] = []
    for c in cands:
        try:
            rp = str(c.resolve())
        except Exception:
            rp = str(c)
        if rp not in vistos and c.exists():
            vistos.add(rp)
            out.append(c)
    return out


def _tem_modulos_midia(py_exe: Path | None = None) -> tuple[bool, list[str]]:
    mods = ("cv2", "PIL", "numpy", "faster_whisper", "yt_dlp")
    if py_exe is None:
        faltando = []
        for m in mods:
            try:
                __import__(m)
            except ImportError:
                faltando.append(m)
        return len(faltando) == 0, faltando

    code = (
        "import json\n"
        "faltando=[]\n"
        f"for m in {mods!r}:\n"
        "  try: __import__(m)\n"
        "  except Exception: faltando.append(m)\n"
        "print(json.dumps(faltando))\n"
    )
    r = subprocess.run([str(py_exe), "-c", code], capture_output=True, text=True)
    if r.returncode != 0:
        return False, list(mods)
    try:
        falt = json.loads(r.stdout.strip())
        return len(falt) == 0, falt
    except Exception:
        return False, list(mods)


def garantir_ambiente_python() -> None:
    """Re-executa automaticamente em um .venv local valido caso o Python atual nao tenha as libs."""
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd in LIGHTWEIGHT_CMDS or cmd in ("-h", "--help", ""):
        return
    ok, _ = _tem_modulos_midia(None)
    if ok:
        return
    atual = Path(sys.executable).resolve()
    for cand in _candidatos_python():
        if cand.resolve() == atual:
            continue
        cand_ok, _ = _tem_modulos_midia(cand)
        if cand_ok:
            raise SystemExit(subprocess.call([str(cand), __file__, *sys.argv[1:]]))


def _registrar_cuda_dlls() -> None:
    """Registra diretorios bin das libs NVIDIA instaladas no .venv no Windows."""
    if sys.platform != "win32":
        return
    venv_site = Path(sys.prefix) / "Lib" / "site-packages"
    bin_dirs = [os.path.abspath(p) for p in glob.glob(str(venv_site / "nvidia" / "*" / "bin"))]
    for d in bin_dirs:
        if os.path.isdir(d):
            try:
                os.add_dll_directory(d)
            except Exception:
                pass
    if bin_dirs:
        os.environ["PATH"] = os.pathsep.join(bin_dirs) + os.pathsep + os.environ.get("PATH", "")


def localizar_binario(nome: str) -> str:
    achado = shutil.which(nome)
    if achado:
        return achado
    try:
        import static_ffmpeg  # type: ignore

        static_ffmpeg.add_paths(weak=True)
        achado = shutil.which(nome)
        if achado:
            return achado
    except Exception:
        pass
    suf = f"{nome}.exe" if os.name == "nt" else nome
    for py in [Path(sys.executable), *_candidatos_python()]:
        cand = py.parent / suf
        if cand.exists():
            return str(cand)
    raise FileNotFoundError(
        f"Executavel '{nome}' nao encontrado no PATH nem nos ambientes locais. Rode `cutter_pipeline.py setup`."
    )


def localizar_chrome() -> str | None:
    env_p = os.environ.get("HYPERFRAMES_BROWSER_PATH")
    if env_p and Path(env_p).exists():
        return env_p
    cands = []
    if os.name == "nt":
        cands = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
    elif sys.platform == "darwin":
        cands = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
            w = shutil.which(b)
            if w:
                return w
    for c in cands:
        if Path(c).exists():
            return c
    return None


def localizar_hyperframes_cli() -> dict[str, str]:
    plugin_cands = [
        Path.home() / ".agents" / "skills" / "hyperframes" / "scripts" / "plugin-cli.mjs",
        Path.home() / ".claude" / "skills" / "hyperframes" / "scripts" / "plugin-cli.mjs",
        Path.home() / ".gemini" / "config" / "skills" / "hyperframes" / "scripts" / "plugin-cli.mjs",
    ]
    for p in plugin_cands:
        if p.exists():
            return {"mode": "plugin-cli", "command": f'node "{p}"'}
    return {"mode": "npx", "command": "npx --yes hyperframes@0.9.72"}


def comando_ytdlp() -> list[str]:
    venv_exe = Path(sys.executable).parent / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
    exe = shutil.which("yt-dlp")
    cmd = [str(venv_exe)] if venv_exe.exists() else ([exe] if exe else [sys.executable, "-m", "yt_dlp"])
    deno_venv = Path(sys.executable).parent / ("deno.exe" if os.name == "nt" else "deno")
    if deno_venv.exists():
        cmd += ["--js-runtimes", f"deno:{deno_venv}"]
    elif shutil.which("deno"):
        cmd += ["--js-runtimes", "deno"]
    elif shutil.which("node"):
        cmd += ["--js-runtimes", "node"]
    return cmd


def resolver_yunet() -> Path | None:
    cands = [
        MODELS_DIR / "face_detection_yunet_2023mar.onnx",
        ASSETS_DIR / "face_detection_yunet_2023mar.onnx",
        Path.home() / "clipper-gta6" / "modelos" / "face_detection_yunet_2023mar.onnx",
    ]
    for p in cands:
        if p.exists():
            return p
    return None


def slugify(texto: str, limite: int = 60) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    return t[:limite].strip("-") or "corte"


def hms_para_segundos(valor: str | float | int) -> float:
    if isinstance(valor, (int, float)):
        return float(valor)
    limpo = str(valor).strip().replace(",", ".")
    partes = [float(p) for p in limpo.split(":")]
    total = 0.0
    for p in partes:
        total = total * 60.0 + p
    return total


def segundos_para_mmss(seg: float) -> str:
    seg = max(0.0, float(seg))
    horas = int(seg // 3600)
    mins = int((seg % 3600) // 60)
    resto = seg - (horas * 3600 + mins * 60)
    if horas > 0:
        return f"{horas:02d}:{mins:02d}:{resto:05.2f}"
    return f"{mins:02d}:{resto:05.2f}"


def _limpar_aspas(texto: str) -> str:
    return re.sub(r"^[\"'`\s]+|[\"'`\s]+$", "", texto.strip())


def _par(v: float) -> int:
    return max(2, int(v) // 2 * 2)


# =====================================================================
# 1. Doctor & Setup Automatico
# =====================================================================
def cmd_doctor(_args: argparse.Namespace) -> None:
    ok_cur, falt_cur = _tem_modulos_midia(None)
    py_escolhido = Path(sys.executable)
    ok_env, falt_env = ok_cur, falt_cur
    if not ok_env:
        for cand in _candidatos_python():
            c_ok, c_falt = _tem_modulos_midia(cand)
            if c_ok:
                py_escolhido = cand
                ok_env, falt_env = True, []
                break
            falt_env = c_falt

    cuda_ok = False
    if ok_env:
        code = (
            "import sys, glob, os; from pathlib import Path\n"
            "if sys.platform=='win32':\n"
            "  for d in glob.glob(str(Path(sys.prefix)/'Lib'/'site-packages'/'nvidia'/'*'/'bin')):\n"
            "    os.add_dll_directory(d)\n"
            "import ctranslate2\n"
            "print(ctranslate2.get_cuda_device_count())\n"
        )
        r = subprocess.run([str(py_escolhido), "-c", code], capture_output=True, text=True)
        cuda_ok = r.returncode == 0 and r.stdout.strip().isdigit() and int(r.stdout.strip()) > 0

    ff = None
    fp = None
    try:
        ff = localizar_binario("ffmpeg")
        fp = localizar_binario("ffprobe")
    except Exception:
        pass

    yunet = resolver_yunet()
    chrome = localizar_chrome()
    hf_cli = localizar_hyperframes_cli()

    payload = {
        "ok": bool(ok_env and ff and fp and yunet and shutil.which("node")),
        "skill_dir": str(SKILL_DIR),
        "python_selected": str(py_escolhido),
        "python_media_ready": ok_env,
        "missing_python_modules": falt_env,
        "cuda_available": cuda_ok,
        "ffmpeg": ff,
        "ffprobe": fp,
        "yunet_model": str(yunet) if yunet else None,
        "chrome_browser": chrome,
        "node": shutil.which("node"),
        "hyperframes_cli": hf_cli,
        "bundled_assets": {
            "montserrat": (FONTS_DIR / "Montserrat-ExtraBold.ttf").exists(),
            "anton": (FONTS_DIR / "Anton-Regular.ttf").exists(),
            "paper_banner": (GRAPHICS_DIR / "torn_paper_banner_base.png").exists(),
            "sfx_count": len(list(SFX_DIR.glob("*"))),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_setup(args: argparse.Namespace) -> None:
    venv_dir = Path(args.venv_dir).resolve() if args.venv_dir else (Path.cwd() / ".venv")
    exe_rel = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    py_venv = venv_dir / exe_rel

    uv = shutil.which("uv")
    if not py_venv.exists():
        if uv:
            subprocess.run([uv, "venv", str(venv_dir)], check=True)
        else:
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    pkgs = ["faster-whisper", "opencv-python", "pillow", "numpy", "yt-dlp", "static-ffmpeg"]
    tem_nvidia = shutil.which("nvidia-smi") is not None
    if tem_nvidia and sys.platform in ("win32", "linux"):
        pkgs += ["nvidia-cublas-cu12", "nvidia-cudnn-cu12", "nvidia-cuda-nvrtc-cu12"]

    if uv:
        subprocess.run([uv, "pip", "install", "--python", str(py_venv), *pkgs], check=True)
    else:
        subprocess.run([str(py_venv), "-m", "pip", "install", "--upgrade", "pip"], check=False)
        subprocess.run([str(py_venv), "-m", "pip", "install", *pkgs], check=True)

    print(json.dumps({"venv": str(venv_dir), "python": str(py_venv), "installed": pkgs}, ensure_ascii=False, indent=2))


# =====================================================================
# 2. Parser de Arquivos .md (Timestamps + Ganchos)
# =====================================================================
def parse_repurpose_md(md_path: Path) -> dict:
    texto = Path(md_path).read_text(encoding="utf-8")
    linhas = texto.splitlines()

    titulo_video = md_path.stem
    fonte = ""
    for ln in linhas:
        s = ln.strip()
        if s.startswith("# ") and titulo_video == md_path.stem:
            titulo_video = s[2:].strip()
        elif s.lower().startswith("fonte:") or s.lower().startswith("- **fonte:**"):
            resto = s.split(":", 1)[1].strip().lstrip("*").strip()
            fonte = resto.split("·")[0].strip()

    blocos: list[dict] = []
    atual: dict | None = None
    re_sec = re.compile(r"^###\s+(\d+)\.\s+(.+?)\s*$")
    re_intervalo = re.compile(
        r"([0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?(?:[.,]\d+)?)\s*(?:→|->|-|a)\s*([0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?(?:[.,]\d+)?)"
    )

    for ln in linhas:
        s = ln.strip()
        m_sec = re_sec.match(s)
        if m_sec:
            if atual is not None:
                blocos.append(atual)
            atual = {
                "numero": int(m_sec.group(1)),
                "titulo_secao": m_sec.group(2).strip(),
                "slug": slugify(m_sec.group(2)),
                "inicio_hms": "",
                "fim_hms": "",
                "inicio_s": 0.0,
                "fim_s": 0.0,
                "comeca_em": "",
                "termina_em": "",
                "por_que_funciona": "",
                "gancho": "",
                "destaques": "",
            }
            continue

        if s.startswith("## ") and atual is not None:
            blocos.append(atual)
            atual = None
            continue

        if atual is None:
            continue

        low = s.lower()
        if "intervalo:" in low or "timestamp:" in low:
            m_int = re_intervalo.search(s)
            if m_int:
                atual["inicio_hms"] = m_int.group(1)
                atual["fim_hms"] = m_int.group(2)
                atual["inicio_s"] = hms_para_segundos(m_int.group(1))
                atual["fim_s"] = hms_para_segundos(m_int.group(2))
        elif "**começa em:**" in low or "**comeca em:**" in low:
            atual["comeca_em"] = _limpar_aspas(s.split("**", 2)[-1].lstrip(":").strip())
        elif "**termina em:**" in low:
            atual["termina_em"] = _limpar_aspas(s.split("**", 2)[-1].lstrip(":").strip())
        elif "**por que funciona:**" in low or "**contexto:**" in low:
            atual["por_que_funciona"] = s.split("**", 2)[-1].lstrip(":").strip()
        elif "**gancho" in low:
            atual["gancho"] = s.split(":**", 1)[-1].strip() if ":**" in s else s.split("**", 2)[-1].lstrip(":").strip()
        elif "**destaques" in low:
            atual["destaques"] = s.split(":**", 1)[-1].strip() if ":**" in s else ""

    if atual is not None:
        blocos.append(atual)

    if not blocos:
        for ln in linhas:
            if "|" not in ln:
                continue
            cols = [c.strip() for c in ln.strip("|").split("|")]
            if len(cols) >= 3 and cols[0].isdigit():
                m_int = re_intervalo.search(cols[2])
                if m_int:
                    gancho_col = cols[3] if len(cols) > 3 else ""
                    blocos.append(
                        {
                            "numero": int(cols[0]),
                            "titulo_secao": cols[1],
                            "slug": slugify(cols[1]),
                            "inicio_hms": m_int.group(1),
                            "fim_hms": m_int.group(2),
                            "inicio_s": hms_para_segundos(m_int.group(1)),
                            "fim_s": hms_para_segundos(m_int.group(2)),
                            "comeca_em": _limpar_aspas(cols[4]) if len(cols) > 4 else "",
                            "termina_em": "",
                            "por_que_funciona": "",
                            "gancho": gancho_col,
                            "destaques": "",
                        }
                    )

    for b in blocos:
        if not b["gancho"]:
            b["gancho"] = b["slug"].replace("-", " ").upper()

    return {"titulo": titulo_video, "fonte": fonte, "momentos": blocos}


# =====================================================================
# 3. Ingestao de Midia, Facecam YuNet, Split Vertical e Whisper
# =====================================================================
def tem_video_valido(arq: Path) -> bool:
    if not arq.exists():
        return False
    ffprobe = localizar_binario("ffprobe")
    r = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v",
            "-count_packets",
            "-show_entries",
            "stream=nb_read_packets",
            "-of",
            "csv=p=0",
            str(arq),
        ],
        capture_output=True,
        text=True,
    )
    txt = r.stdout.strip()
    return txt.isdigit() and int(txt) > 10


def medir_midia(arq: Path) -> tuple[float, int, int]:
    ffprobe = localizar_binario("ffprobe")
    out = subprocess.check_output(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(arq),
        ],
        text=True,
    )
    data = json.loads(out)
    dur = float(data["format"]["duration"])
    w, h = 0, 0
    for st in data.get("streams", []):
        if st.get("codec_type") == "video":
            w, h = int(st.get("width", 0)), int(st.get("height", 0))
            break
    return dur, w, h


def baixar_ou_recortar_trecho(
    fonte: str,
    s: float | None,
    e: float | None,
    destino: Path,
    apenas_audio: bool = False,
) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = localizar_binario("ffmpeg")
    caminho_local = Path(fonte)

    if caminho_local.exists() and caminho_local.is_file():
        if s is None and e is None and not apenas_audio:
            shutil.copy2(caminho_local, destino)
            return
        cmd = [ffmpeg, "-y", "-loglevel", "error"]
        if s is not None and s > 0:
            cmd += ["-ss", f"{s:.3f}"]
        cmd += ["-i", str(caminho_local)]
        if e is not None:
            dur = max(0.5, e - (s or 0.0))
            cmd += ["-t", f"{dur:.3f}"]
        if apenas_audio:
            cmd += ["-vn", "-c:a", "aac", "-b:a", "160k", str(destino)]
        else:
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", str(destino)]
        subprocess.run(cmd, check=True)
        return

    ytdlp = comando_ytdlp()
    tem_corte = s is not None and e is not None
    if apenas_audio:
        extra = ["--download-sections", f"*{s:.2f}-{e:.2f}"] if tem_corte else []
        subprocess.run(
            ytdlp + ["-f", FORMATO_AUDIO_YTDLP, "--no-playlist", "--no-warnings", "-q", *extra, "-o", str(destino), fonte],
            check=True,
            timeout=3600,
        )
        return

    for fmt in (FORMATO_YTDLP, FORMATO_YTDLP_HLS):
        try:
            extra = ["--download-sections", f"*{s:.2f}-{e:.2f}", "--force-keyframes-at-cuts"] if tem_corte else []
            subprocess.run(
                ytdlp
                + [
                    "-f",
                    fmt,
                    "--no-playlist",
                    "--no-warnings",
                    "-q",
                    *extra,
                    "--merge-output-format",
                    "mp4",
                    "-o",
                    str(destino),
                    fonte,
                ],
                check=True,
                timeout=3600,
            )
            if destino.exists() and tem_video_valido(destino):
                return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            destino.unlink(missing_ok=True)

    if tem_corte:
        assert s is not None and e is not None
        dur = max(1.0, e - s)
        r = subprocess.run(
            ytdlp + ["-f", FORMATO_YTDLP, "-g", "--no-playlist", "--no-warnings", fonte],
            capture_output=True,
            text=True,
        )
        links = [ln.strip() for ln in r.stdout.splitlines() if ln.strip().startswith("http")]
        if links:
            entrada: list[str] = []
            for lk in links[:2]:
                entrada += ["-ss", f"{s:.2f}", "-i", lk]
            mapa = ["-map", "0:v:0", "-map", f"{len(links[:2]) - 1}:a:0?"]
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-loglevel",
                    "error",
                    *entrada,
                    "-t",
                    f"{dur:.2f}",
                    *mapa,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "16",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    str(destino),
                ],
                check=True,
                timeout=1800,
            )
            if destino.exists() and tem_video_valido(destino):
                return

    destino.unlink(missing_ok=True)
    raise RuntimeError(f"Nao foi possivel baixar/recortar midia de: {fonte}")


def detectar_facecam(video: Path) -> tuple[int, int, tuple[float, float, float, float] | None]:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(video))
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    yunet = resolver_yunet()
    if yunet is None or W <= 0 or H <= 0:
        cap.release()
        return W, H, None

    esc = 960.0 / W
    det = cv2.FaceDetectorYN.create(str(yunet), "", (960, max(2, int(H * esc))), 0.70)
    caixas: list[tuple[int, list[float]]] = []
    rostos_grandes = 0
    for k in range(20):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (k + 0.5) / 20))
        ok, frame = cap.read()
        if not ok:
            continue
        _, rostos = det.detect(cv2.resize(frame, (960, max(2, int(H * esc)))))
        for r in rostos if rostos is not None else []:
            if r[14] < 0.72:
                continue
            h_orig = float(r[3]) / esc
            if h_orig > H * 0.25:
                rostos_grandes += 1
            elif H * 0.055 <= h_orig <= H * 0.25:
                caixas.append((k, [float(v) / esc for v in r[:4]]))
    cap.release()

    min_quadros = 6 if rostos_grandes >= 4 else 4
    if len(caixas) < min_quadros:
        return W, H, None

    frames_idx = np.array([c[0] for c in caixas], dtype=np.int32)
    arr = np.array([c[1] for c in caixas], dtype=np.float32)
    centros = arr[:, :2] + arr[:, 2:] / 2.0
    raio = W * 0.075
    candidatos = []
    for i in range(len(arr)):
        mask = np.linalg.norm(centros - centros[i], axis=1) < raio
        n_unicos = len(np.unique(frames_idx[mask]))
        if n_unicos < min_quadros:
            continue
        grupo = arr[mask]
        med = np.median(grupo, axis=0)
        fx, fy, fw, fh = med
        cx_n, cy_n, fh_n = (fx + fw / 2.0) / W, (fy + fh / 2.0) / H, fh / H
        spread = float(
            np.mean(np.linalg.norm((grupo[:, :2] + grupo[:, 2:] / 2.0) - np.array([fx + fw / 2.0, fy + fh / 2.0]), axis=1))
        )
        if spread > W * 0.035:
            continue
        na_borda = cx_n < 0.38 or cx_n > 0.62 or cy_n < 0.42 or cy_n > 0.65
        if (na_borda and fh_n <= 0.25) or (fh_n <= 0.20 and spread < W * 0.025):
            candidatos.append((n_unicos, -spread, (float(fx), float(fy), float(fw), float(fh))))

    if not candidatos:
        return W, H, None
    candidatos.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return W, H, candidatos[0][2]


def calcular_crop_facecam(W: int, H: int, rosto: tuple[float, float, float, float], cam_h: int) -> tuple[int, int, int, int]:
    fx, fy, fw, fh = rosto
    ch = min(H * 0.225, max(fh * 1.55, H * 0.18))
    cw = ch * CANVAS_W / cam_h
    if cw > W:
        cw, ch = W, W * cam_h / CANVAS_W
    mx = 12 if W >= 1280 else 4
    my = 12 if H >= 720 else 4
    cx = min(max(fx + fw / 2 - cw / 2, mx), max(0.0, W - cw - mx))
    cy = min(max(fy + fh * 0.55 - ch / 2, my), max(0.0, H - ch - my))
    return _par(cw), _par(ch), _par(cx), _par(cy)


def gerar_split_vertical(
    bruto: Path,
    destino_mp4: Path,
    duracao_alvo: float | None = None,
    facecam_mode: str = "auto",
    cam_h: int = 768,
) -> tuple[bool, float]:
    ffmpeg = localizar_binario("ffmpeg")
    game_h = CANVAS_H - cam_h
    dur_orig, W, H = medir_midia(bruto)
    dur_final = min(dur_orig, duracao_alvo) if duracao_alvo else dur_orig

    rosto: tuple[float, float, float, float] | None = None
    if facecam_mode == "none":
        rosto = None
    elif facecam_mode == "auto":
        W, H, rosto = detectar_facecam(bruto)
    else:
        partes = [float(x.strip()) for x in facecam_mode.split(",")]
        if len(partes) != 4:
            raise ValueError("--facecam deve ser 'auto', 'none' ou 'x,y,w,h'")
        rosto = (partes[0], partes[1], partes[2], partes[3])

    if rosto is None:
        filtro_v = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:3[bg];"
            "[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[v]"
        )
    else:
        cw, ch, cx, cy = calcular_crop_facecam(W, H, rosto, cam_h)
        gw = min(W, H * CANVAS_W / game_h)
        gh = min(H, W * game_h / CANVAS_W)
        gx = (W - gw) / 2.0
        gy = (H - gh) / 2.0
        filtro_v = (
            f"[0:v]crop={cw}:{ch}:{cx}:{cy},scale={CANVAS_W}:{cam_h},setsar=1[cam];"
            f"[0:v]crop={_par(gw)}:{_par(gh)}:{_par(gx)}:{_par(gy)},scale={CANVAS_W}:{game_h},setsar=1[jogo];"
            f"[cam][jogo]vstack=inputs=2,format=yuv420p[v]"
        )

    destino_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(bruto),
        "-t",
        f"{dur_final:.3f}",
        "-filter_complex",
        filtro_v,
        "-map",
        "[v]",
        "-map",
        "0:a:0?",
        "-af",
        "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FPS),
        "-g",
        "15",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        str(destino_mp4),
    ]
    subprocess.run(cmd, check=True)
    dur_real, _, _ = medir_midia(destino_mp4)
    return rosto is not None, dur_real


_WHISPER_MODEL_CACHE: dict[tuple[str, str, str], object] = {}


def _obter_whisper(modelo: str):
    _registrar_cuda_dlls()
    from faster_whisper import WhisperModel

    device, compute = "cpu", "int8"
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            device, compute = "cuda", "float16"
    except Exception:
        pass

    key = (modelo, device, compute)
    wm = _WHISPER_MODEL_CACHE.get(key)
    if wm is None:
        try:
            wm = WhisperModel(modelo, device=device, compute_type=compute)
            _WHISPER_MODEL_CACHE[key] = wm
        except Exception:
            fb_key = (modelo, "cpu", "int8")
            wm = _WHISPER_MODEL_CACHE.get(fb_key)
            if wm is None:
                wm = WhisperModel(modelo, device="cpu", compute_type="int8")
                _WHISPER_MODEL_CACHE[fb_key] = wm
            device, compute = "cpu", "int8"
    return wm, device, compute


def transcrever_completo(midia: Path, idioma: str | None = "pt", modelo: str = "large-v3-turbo") -> dict:
    """Transcreve arquivo completo retornando estrutura JSON rica (segments + words)."""
    import numpy as np

    ffmpeg = localizar_binario("ffmpeg")
    proc = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(midia), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True,
        check=True,
    )
    audio = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if audio.size < 1600:
        return {"language": idioma or "pt", "duration": 0.0, "model": modelo, "segments": [], "words": []}

    wm, device, compute = _obter_whisper(modelo)

    def _exec(vad: bool):
        segs_iter, info = wm.transcribe(
            audio,
            language=idioma or None,
            word_timestamps=True,
            vad_filter=vad,
            condition_on_previous_text=False,
        )
        segs, words = [], []
        for seg in segs_iter:
            sw = []
            for w in seg.words or []:
                wt = w.word.strip()
                if wt:
                    we = {
                        "word": wt,
                        "text": wt,
                        "start": round(float(w.start), 3),
                        "end": round(float(w.end), 3),
                        "probability": round(float(w.probability), 4),
                    }
                    sw.append(we)
                    words.append(we)
            segs.append(
                {
                    "id": seg.id,
                    "start": round(float(seg.start), 3),
                    "end": round(float(seg.end), 3),
                    "text": seg.text.strip(),
                    "words": sw,
                }
            )
        return segs, words, info

    segs, words, info = _exec(True)
    if len(words) < 8:
        segs2, words2, info2 = _exec(False)
        if len(words2) > len(words):
            segs, words, info = segs2, words2, info2

    return {
        "language": info.language,
        "language_probability": round(float(info.language_probability), 4),
        "duration": round(float(info.duration), 3),
        "model": modelo,
        "device": device,
        "compute_type": compute,
        "segments": segs,
        "words": words,
    }


def transcrever_palavras(video: Path, idioma: str | None = "pt", modelo: str = "large-v3-turbo") -> list[dict]:
    dados = transcrever_completo(video, idioma=idioma, modelo=modelo)
    return [{"text": w["text"], "start": w["start"], "end": w["end"]} for w in dados["words"]]


def agrupar_legendas(palavras: list[dict], dur_total: float, max_end: float | None = None) -> list[dict]:
    """Agrupa palavras em blocos curtos (ate 3 palavras / 19 chars), garantindo start < end estrito."""
    if not palavras:
        return []
    teto = min(dur_total, max_end) if max_end is not None else dur_total
    filtradas = [w for w in palavras if w["start"] < teto - 0.12]
    if not filtradas:
        return []

    grupos_raw: list[list[dict]] = []
    atual: list[dict] = []
    for i, w in enumerate(filtradas):
        prev = filtradas[i - 1] if i > 0 else None
        gap = (w["start"] - prev["end"]) if prev else 0.0
        punct = prev["text"].endswith((".", "!", "?")) if prev else False
        len_atual = sum(len(x["text"]) + 1 for x in atual)
        if atual and (len(atual) >= 3 or gap > 0.50 or punct or len_atual + len(w["text"]) > 19):
            grupos_raw.append(atual)
            atual = []
        atual.append(w)
    if atual:
        grupos_raw.append(atual)

    saida = []
    for idx, grp in enumerate(grupos_raw):
        prox = grupos_raw[idx + 1] if idx + 1 < len(grupos_raw) else None
        ultimo = grp[-1]
        prox_ini = prox[0]["start"] if prox else min(teto, ultimo["end"] + 0.26)
        fim_grp = min(teto, prox_ini if (prox_ini - ultimo["end"]) < 0.50 else ultimo["end"] + 0.25)
        g_start = max(0.05, round(grp[0]["start"], 3))
        if fim_grp <= g_start + 0.08:
            continue
        words_out = []
        for wi, item in enumerate(grp):
            w_start = max(0.05, round(item["start"], 3))
            if w_start >= fim_grp - 0.04:
                continue
            raw_end = grp[wi + 1]["start"] if wi + 1 < len(grp) else fim_grp
            w_end = round(max(w_start + 0.08, min(raw_end, fim_grp)), 3)
            words_out.append({"text": item["text"].upper(), "start": w_start, "end": w_end})
        if words_out:
            g_end = round(max(words_out[-1]["end"], min(fim_grp, teto)), 3)
            if g_end > words_out[0]["start"]:
                saida.append({"start": words_out[0]["start"], "end": g_end, "words": words_out})
    return saida


# =====================================================================
# 4. Extracao e Evidencias Visuais (Curadoria para Lote ou Hibrido)
# =====================================================================
def gerar_contact_sheet(
    video: Path,
    destino_jpg: Path,
    inicio_s: float = 0.0,
    fim_s: float | None = None,
    step_s: float = 5.0,
    cols: int = 4,
    thumb_w: int = 420,
) -> Path:
    ffmpeg = localizar_binario("ffmpeg")
    dur_total, _, _ = medir_midia(video)
    s0 = max(0.0, inicio_s)
    s1 = min(dur_total, fim_s) if fim_s is not None else dur_total
    janela = max(1.0, s1 - s0)
    n_frames = max(1, min(36, int(janela / max(0.2, step_s)) + 1))
    rows = max(1, (n_frames + cols - 1) // cols)
    fps_val = n_frames / janela

    destino_jpg.parent.mkdir(parents=True, exist_ok=True)
    vf = f"fps={fps_val:.5f},scale={thumb_w}:-2,tile={cols}x{rows}:padding=6:margin=6:color=black"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{s0:.3f}",
            "-i",
            str(video),
            "-t",
            f"{janela:.3f}",
            "-vf",
            vf,
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(destino_jpg),
        ],
        check=True,
    )
    return destino_jpg


def cmd_extract(args: argparse.Namespace) -> None:
    saida_dir = Path(args.saida_dir).resolve()
    saida_dir.mkdir(parents=True, exist_ok=True)
    s0 = hms_para_segundos(args.inicio) if args.inicio is not None else None
    s1 = hms_para_segundos(args.fim) if args.fim is not None else None

    midia_local = saida_dir / ("audio.m4a" if args.apenas_audio else "source.mp4")
    baixar_ou_recortar_trecho(args.fonte, s0, s1, midia_local, apenas_audio=args.apenas_audio)

    tr = transcrever_completo(midia_local, idioma=args.idioma, modelo=args.whisper_modelo)
    offset = s0 or 0.0
    tr_json_path = saida_dir / "transcript.json"
    tr_json_path.write_text(json.dumps(tr, ensure_ascii=False, indent=2), encoding="utf-8")

    linhas_txt = []
    for idx, seg in enumerate(tr["segments"], start=1):
        abs_s = seg["start"] + offset
        abs_e = seg["end"] + offset
        tag_abs = f" (fonte {segundos_para_mmss(abs_s)} -> {segundos_para_mmss(abs_e)})" if offset > 0 else ""
        linhas_txt.append(
            f"{idx:03d} [{segundos_para_mmss(seg['start'])} -> {segundos_para_mmss(seg['end'])}]{tag_abs} {seg['text']}"
        )
    tr_lines_path = saida_dir / "transcript_lines.txt"
    tr_lines_path.write_text("\n".join(linhas_txt) + "\n", encoding="utf-8")

    overview_path = None
    facecam_info = None
    if not args.apenas_audio and tem_video_valido(midia_local):
        ev_dir = saida_dir / "evidence"
        dur, W, H = medir_midia(midia_local)
        step = args.grid_step if args.grid_step > 0 else max(2.0, round(dur / 24.0, 1))
        overview_path = str(gerar_contact_sheet(midia_local, ev_dir / "overview.jpg", 0.0, dur, step_s=step))
        _, _, rosto = detectar_facecam(midia_local)
        if rosto is not None:
            cw600, ch600, cx600, cy600 = calcular_crop_facecam(W, H, rosto, 600)
            cw768, ch768, cx768, cy768 = calcular_crop_facecam(W, H, rosto, 768)
            facecam_info = {
                "detected": True,
                "source_size": [W, H],
                "face_bbox": [round(x, 1) for x in rosto],
                "suggested_crop_600": f"crop={cw600}:{ch600}:{cx600}:{cy600},scale=1080:600,setsar=1",
                "suggested_crop_768": f"crop={cw768}:{ch768}:{cx768}:{cy768},scale=1080:768,setsar=1",
            }
        else:
            facecam_info = {"detected": False, "source_size": [W, H]}

    print(
        json.dumps(
            {
                "midia": str(midia_local),
                "offset_fonte_s": offset,
                "duracao_s": tr["duration"],
                "segmentos": len(tr["segments"]),
                "palavras": len(tr["words"]),
                "transcript_json": str(tr_json_path),
                "transcript_lines": str(tr_lines_path),
                "overview_jpg": overview_path,
                "facecam": facecam_info,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def cmd_evidence(args: argparse.Namespace) -> None:
    vid = Path(args.video).resolve()
    s0 = hms_para_segundos(args.inicio) if args.inicio is not None else 0.0
    s1 = hms_para_segundos(args.fim) if args.fim is not None else None
    out = Path(args.saida).resolve()
    gerar_contact_sheet(vid, out, inicio_s=s0, fim_s=s1, step_s=args.step, cols=args.cols)
    print(json.dumps({"evidence": str(out), "inicio_s": s0, "fim_s": s1, "step_s": args.step}, ensure_ascii=False))


def cmd_detect_cam(args: argparse.Namespace) -> None:
    vid = Path(args.video).resolve()
    W, H, rosto = detectar_facecam(vid)
    if rosto is None:
        print(json.dumps({"detected": False, "width": W, "height": H}, ensure_ascii=False, indent=2))
        return
    cw600, ch600, cx600, cy600 = calcular_crop_facecam(W, H, rosto, 600)
    cw768, ch768, cx768, cy768 = calcular_crop_facecam(W, H, rosto, 768)
    print(
        json.dumps(
            {
                "detected": True,
                "width": W,
                "height": H,
                "face_bbox": [round(x, 1) for x in rosto],
                "crop_600": f"crop={cw600}:{ch600}:{cx600}:{cy600},scale=1080:600,setsar=1",
                "crop_768": f"crop={cw768}:{ch768}:{cx768}:{cy768},scale=1080:768,setsar=1",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


# =====================================================================
# 5. Banner de Papel 3D e Runtimes JS Deterministicos
# =====================================================================
def _tokenizar_gancho(texto: str) -> list[tuple[str, bool]]:
    tokens: list[tuple[str, bool]] = []
    limpo = re.sub(r"\s+", " ", texto.strip())
    if "*" not in limpo:
        return [(w, False) for w in limpo.upper().split()]
    partes = re.split(r"(\*[^*]+\*)", limpo)
    for p in partes:
        if not p:
            continue
        eh_destaque = p.startswith("*") and p.endswith("*") and len(p) > 2
        val = p[1:-1] if eh_destaque else p
        for pedaco in val.split():
            tokens.append((pedaco.upper(), eh_destaque))
    return tokens


def _quebrar_tokens_em_linhas(draw, tokens: list[tuple[str, bool]], fonte, max_w: int) -> list[list[tuple[str, bool]]]:
    linhas: list[list[tuple[str, bool]]] = []
    atual: list[tuple[str, bool]] = []
    for tok in tokens:
        cand = atual + [tok]
        str_cand = " ".join(t[0] for t in cand)
        bx = draw.textbbox((0, 0), str_cand, font=fonte, stroke_width=6)
        if bx[2] - bx[0] <= max_w or not atual:
            atual = cand
        else:
            linhas.append(atual)
            atual = [tok]
    if atual:
        linhas.append(atual)
    return linhas


def gerar_png_banner_enrolando(
    texto: str,
    destino_png: Path,
    *,
     escurecer_fundo: bool = False,
    base_png: Path | None = None,
    fonte_ttf: Path | None = None,
) -> None:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    base_path = base_png or (GRAPHICS_DIR / "torn_paper_banner_base.png")
    font_path = fonte_ttf or (FONTS_DIR / "Montserrat-ExtraBold.ttf")
    img = Image.open(base_path).convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    ys = np.where((alpha > 10).any(axis=1))[0]
    xs = np.where((alpha > 10).any(axis=0))[0]
    cropped = img.crop(
        (max(0, int(xs[0]) - 4), max(0, int(ys[0]) - 4), min(arr.shape[1], int(xs[-1]) + 5), min(arr.shape[0], int(ys[-1]) + 5))
    )
    largura_alvo = 1016
    nova_h = max(2, int(round(cropped.height * (largura_alvo / cropped.width))))
    faixa = cropped.resize((largura_alvo, nova_h), Image.Resampling.LANCZOS)

    if escurecer_fundo:
        tint = Image.new("RGBA", faixa.size, (15, 6, 28, 78))
        tint_arr = np.array(tint)
        tint_arr[:, :, 3] = np.minimum(tint_arr[:, :, 3], np.array(faixa.getchannel("A")))
        faixa = Image.alpha_composite(faixa, Image.fromarray(tint_arr))

    has_star = "*" in texto
    tokens = _tokenizar_gancho(texto)

    camada = Image.new("RGBA", faixa.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(camada)
    safe_w = int(largura_alvo * 0.68)
    safe_h = int(nova_h * 0.62)

    melhor_fonte = None
    melhor_linhas: list[list[tuple[str, bool]]] = []
    melhor_heights: list[int] = []
    espaco_linhas = 8

    for max_linhas in (2, 3):
        for tam in range(52, 26, -2):
            fnt = ImageFont.truetype(str(font_path), tam)
            linhas = _quebrar_tokens_em_linhas(draw, tokens, fnt, safe_w)
            if not linhas or len(linhas) > max_linhas:
                continue
            largs, alts = [], []
            for ln in linhas:
                txt_ln = " ".join(t[0] for t in ln)
                bx = draw.textbbox((0, 0), txt_ln, font=fnt, stroke_width=6)
                largs.append(bx[2] - bx[0])
                alts.append(bx[3] - bx[1])
            tot_h = sum(alts) + espaco_linhas * (len(linhas) - 1)
            if max(largs) <= safe_w and tot_h <= safe_h:
                melhor_fonte, melhor_linhas, melhor_heights = fnt, linhas, alts
                break
        if melhor_fonte is not None:
            break

    if melhor_fonte is None:
        melhor_fonte = ImageFont.truetype(str(font_path), 28)
        melhor_linhas = _quebrar_tokens_em_linhas(draw, tokens, melhor_fonte, safe_w)
        melhor_heights = [
            draw.textbbox((0, 0), " ".join(t[0] for t in ln), font=melhor_fonte, stroke_width=5)[3] for ln in melhor_linhas
        ]

    tot_h = sum(melhor_heights) + espaco_linhas * (len(melhor_linhas) - 1)
    y_atual = (nova_h - tot_h) // 2 - 4
    cx = largura_alvo // 2
    space_w = int(draw.textlength(" ", font=melhor_fonte))

    for idx, ln in enumerate(melhor_linhas):
        txt_ln = " ".join(t[0] for t in ln)
        bx_full = draw.textbbox((0, 0), txt_ln, font=melhor_fonte, stroke_width=6)
        full_w = bx_full[2] - bx_full[0]
        th = bx_full[3] - bx_full[1]
        x_cursor = cx - full_w // 2 - bx_full[0]
        ty = y_atual - bx_full[1]
        for palavra, hi in ln:
            if has_star:
                cor = "#FFE500" if hi else "#FFFFFF"
            else:
                cor = "#FFE500" if (len(melhor_linhas) >= 2 and idx == len(melhor_linhas) - 1) else "#FFFFFF"
            draw.text(
                (x_cursor, ty + 4),
                palavra,
                font=melhor_fonte,
                fill=(10, 8, 20, 195),
                stroke_width=6,
                stroke_fill=(10, 8, 20, 195),
            )
            draw.text((x_cursor, ty), palavra, font=melhor_fonte, fill=cor, stroke_width=6, stroke_fill="#0B0914")
            x_cursor += int(draw.textlength(palavra, font=melhor_fonte)) + space_w
        y_atual += th + espaco_linhas

    a_papel = faixa.getchannel("A")
    cam_arr = np.array(camada)
    cam_arr[:, :, 3] = np.minimum(cam_arr[:, :, 3], np.array(a_papel))
    faixa_final = Image.alpha_composite(faixa, Image.fromarray(cam_arr))

    canvas = Image.new("RGBA", (CANVAS_W, 520), (0, 0, 0, 0))
    canvas.paste(faixa_final, ((CANVAS_W - faixa_final.width) // 2, (520 - faixa_final.height) // 2), faixa_final)
    destino_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destino_png)


PAPER_ROLL_CORE_JS = r"""
function clamp01(v) { return Math.max(0, Math.min(1, v)); }
function easeInOut(t) { t = clamp01(t); return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }
function cubicBezier042(t) { t = clamp01(t); return Math.pow(t, 1.38) * (3 - 2 * t); }
function interp(t, pts, vals, easeFn) {
  if (t <= pts[0]) return vals[0];
  if (t >= pts[pts.length - 1]) return vals[vals.length - 1];
  for (let i = 0; i < pts.length - 1; i++) {
    if (t >= pts[i] && t <= pts[i + 1]) {
      const span = Math.max(1e-6, pts[i + 1] - pts[i]);
      const p = (t - pts[i]) / span;
      const e = easeFn ? easeFn(p) : p;
      return vals[i] + (vals[i + 1] - vals[i]) * e;
    }
  }
  return vals[vals.length - 1];
}
function drawBackPaper(backCtx, source, width, height) {
  backCtx.clearRect(0, 0, width, height);
  backCtx.globalCompositeOperation = 'source-over';
  backCtx.globalAlpha = 1;
  backCtx.drawImage(source, 0, 0, width, height);
  backCtx.globalCompositeOperation = 'source-atop';
  backCtx.globalAlpha = 0.78;
  backCtx.fillStyle = '#f5efe6';
  backCtx.fillRect(0, 0, width, height);
  backCtx.globalAlpha = 1;
  for (let i = 0; i < 140; i++) {
    const h1 = ((i * 1664525 + 1013904223) >>> 0) / 4294967296;
    const h2 = (((i + 37) * 22695477 + 1) >>> 0) / 4294967296;
    const h3 = (((i + 91) * 1103515245 + 12345) >>> 0) / 4294967296;
    backCtx.strokeStyle = i % 2 === 0 ? 'rgba(98,82,64,0.085)' : 'rgba(255,255,255,0.16)';
    backCtx.lineWidth = 1 + (i % 3) * 0.4;
    backCtx.beginPath();
    backCtx.moveTo(h1 * width, h2 * height);
    backCtx.lineTo(h1 * width + 8 + h3 * 22, h2 * height + (h3 - 0.5) * 4);
    backCtx.stroke();
  }
  backCtx.globalCompositeOperation = 'source-over';
}
function createPaperRollRenderer(canvasId, imgSrc, totalSec) {
  const target = document.getElementById(canvasId);
  if (!target) return { loadPromise: Promise.resolve(), renderAt: () => {} };
  const width = target.width, height = target.height;
  const targetCtx = target.getContext('2d');
  const off = () => { const c = document.createElement('canvas'); c.width = width; c.height = height; return c; };
  const backCanvas = off(), flatCanvas = off(), workCanvas = off(), compCanvas = off();
  const backCtx = backCanvas.getContext('2d'), flatCtx = flatCanvas.getContext('2d');
  const workCtx = workCanvas.getContext('2d'), compCtx = compCanvas.getContext('2d');
  const endF = Math.max(45, Math.round((totalSec - 0.05) * 30));
  const inF = Math.min(16, Math.max(10, Math.round(endF * 0.10)));
  const outStartF = Math.max(inF + 12, endF - Math.min(31, Math.max(18, Math.round(endF * 0.18))));

  let ready = false;
  const img = new Image();
  const loadPromise = new Promise((resolve) => {
    img.onload = () => { drawBackPaper(backCtx, img, width, height); ready = true; renderAt(0); resolve(); };
    img.onerror = () => resolve();
  });
  img.src = imgSrc;

  function renderAt(t) {
    targetCtx.clearRect(0, 0, width, height);
    if (!ready || t >= totalSec - 0.02) return;
    const frame = t * 30;
    const progress = interp(frame, [0, inF, outStartF, endF], [1.14, 0, 0, 1.14], cubicBezier042);
    const mid1 = Math.round(inF + (outStartF - inF) * 0.33);
    const mid2 = Math.round(inF + (outStartF - inF) * 0.68);
    const dy = interp(frame, [0, inF, mid1, mid2, outStartF, endF], [0, 0, -3.5, 2.8, 0, 0], easeInOut);
    const rotDeg = interp(frame, [0, inF, mid1, mid2, outStartF, endF - 5, endF], [0, 0, -0.55, 0.45, 0, -1.3, -1.7], easeInOut);
    target.style.transform = `translate3d(0px, ${dy.toFixed(2)}px, 0px) rotate(${rotDeg.toFixed(3)}deg)`;

    if (progress <= 0.0005) {
      targetCtx.shadowColor = 'rgba(0,0,0,0.36)';
      targetCtx.shadowBlur = 18;
      targetCtx.shadowOffsetY = 9;
      targetCtx.drawImage(img, 0, 0, width, height);
      targetCtx.shadowColor = 'transparent';
      return;
    }
    const pLeft = 0.0278 * width, pRight = 0.9722 * width, pWidth = pRight - pLeft, cy = height / 2;
    const rolledLen = progress * pWidth, rollX = pRight - rolledLen;
    const R = 20 + (52 - 20) * Math.sqrt(clamp01(progress));
    if (rollX + R + 28 < 0) return;

    compCtx.clearRect(0, 0, width, height);
    if (rollX > pLeft) {
      flatCtx.clearRect(0, 0, width, height);
      flatCtx.globalCompositeOperation = 'source-over';
      const flatW = Math.min(width, Math.ceil(rollX + 1));
      if (flatW > 0) {
        flatCtx.drawImage(img, 0, 0, flatW, height, 0, 0, flatW, height);
        const s0 = Math.max(0, rollX - R * 1.7), s1 = Math.min(width, rollX + 1);
        const actSh = 0.42 * Math.min(1, rolledLen / (R * 1.1));
        if (s1 > s0 && actSh > 0.001) {
          flatCtx.globalCompositeOperation = 'source-atop';
          const g = flatCtx.createLinearGradient(s0, 0, s1, 0);
          g.addColorStop(0, 'rgba(12,6,18,0)');
          g.addColorStop(0.55, `rgba(12,6,18,${actSh * 0.28})`);
          g.addColorStop(1, `rgba(12,6,18,${actSh})`);
          flatCtx.fillStyle = g;
          flatCtx.fillRect(s0, 0, s1 - s0 + 1, height);
          flatCtx.globalCompositeOperation = 'source-over';
        }
        compCtx.drawImage(flatCanvas, 0, 0);
      }
    }
    workCtx.clearRect(0, 0, width, height);
    workCtx.globalCompositeOperation = 'source-over';
    let drewFront = false;
    const maxDx = Math.ceil(R);
    for (let dx = 0; dx <= maxDx; dx++) {
      const th = Math.asin(Math.min(1, dx / R));
      const raw = rollX + R * th;
      if (raw < pLeft || raw > pRight) continue;
      drewFront = true;
      const dstH = height * (1 + 0.048 * (1 - Math.cos(th)));
      const sw = Math.max(1, Math.min(6, 1 / Math.max(0.2, Math.cos(th))));
      workCtx.drawImage(img, Math.min(width - sw, Math.max(0, raw)), 0, sw, height, rollX + dx, cy - dstH / 2, 1.6, dstH);
    }
    if (drewFront) {
      workCtx.globalCompositeOperation = 'source-atop';
      const fg = workCtx.createLinearGradient(rollX, 0, rollX + R + 1, 0);
      fg.addColorStop(0, 'rgba(10,5,18,0.34)'); fg.addColorStop(0.5, 'rgba(10,5,18,0.14)'); fg.addColorStop(1, 'rgba(10,5,18,0.22)');
      workCtx.fillStyle = fg;
      workCtx.fillRect(Math.floor(rollX - 1), 0, Math.ceil(R + 4), height);
      workCtx.globalCompositeOperation = 'source-over';
      compCtx.drawImage(workCanvas, 0, 0);
    }
    workCtx.clearRect(0, 0, width, height);
    workCtx.globalCompositeOperation = 'source-over';
    const wrapLen = Math.min(pWidth, 2 * Math.PI * R);
    let drewCyl = false;
    for (let dx = -maxDx; dx <= maxDx; dx++) {
      const th = Math.PI - Math.asin(Math.max(-1, Math.min(1, dx / R)));
      let srcX;
      if (rollX >= pLeft) {
        const cand = rollX + R * th;
        if (cand < pLeft || cand > pRight) continue;
        srcX = cand;
      } else {
        const raw = rollX + R * th - pLeft;
        srcX = pLeft + ((raw % wrapLen) + wrapLen) % wrapLen;
      }
      drewCyl = true;
      const dstH = height * (1 + 0.048 * (1 - Math.cos(th)));
      const sw = Math.max(1, Math.min(6, 1 / Math.max(0.2, Math.abs(Math.cos(th)))));
      workCtx.drawImage(backCanvas, Math.min(width - sw, Math.max(0, srcX)), 0, sw, height, rollX + dx, cy - dstH / 2, 1.6, dstH);
    }
    if (drewCyl) {
      workCtx.globalCompositeOperation = 'source-atop';
      const cg = workCtx.createLinearGradient(rollX - R, 0, rollX + R + 1, 0);
      cg.addColorStop(0, 'rgba(18,12,26,0.46)'); cg.addColorStop(0.16, 'rgba(20,14,28,0.20)');
      cg.addColorStop(0.44, 'rgba(255,255,255,0.04)'); cg.addColorStop(0.65, 'rgba(255,253,248,0.30)');
      cg.addColorStop(0.86, 'rgba(20,14,28,0.10)'); cg.addColorStop(1, 'rgba(18,12,26,0.28)');
      workCtx.fillStyle = cg;
      workCtx.fillRect(Math.floor(rollX - R - 2), 0, Math.ceil(R * 2 + 6), height);
      workCtx.globalCompositeOperation = 'source-over';
      compCtx.drawImage(workCanvas, 0, 0);
    }
    targetCtx.shadowColor = 'rgba(0,0,0,0.36)';
    targetCtx.shadowBlur = 18;
    targetCtx.shadowOffsetY = 9;
    targetCtx.drawImage(compCanvas, 0, 0);
    targetCtx.shadowColor = 'transparent';
  }
  return { loadPromise, renderAt, isReady: () => ready };
}
"""

CAPTIONS_RENDER_JS = r"""
function renderCaptionsAt(groups, containerId, t) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const active = groups.find(g => t >= g.start && t < g.end);
  if (!active) { el.innerHTML = ''; return; }
  el.innerHTML = active.words.map((w) => {
    const on = t >= w.start && t < w.end;
    const cls = on ? 'cap-word active' : 'cap-word';
    return `<span class="${cls}" data-layout-allow-safe-zone>${w.text.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</span>`;
  }).join('');
}
"""


# =====================================================================
# 6. Modo 1 — Producao em Lote (Geracao 1: Individual & TOP)
# =====================================================================
def gerar_projeto_hf_individual(
    projeto_dir: Path,
    video_split: Path,
    banner_png: Path,
    duracao: float,
    grupos_legenda: list[dict],
    gancho_texto: str,
    legenda_y: int = 1140,
    banner_dur: float = 5.92,
) -> Path:
    assets = projeto_dir / "assets"
    fonts_dir = assets / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(video_split, assets / "video_split.mp4")
    shutil.copy2(banner_png, assets / "banner_gancho.png")
    shutil.copy2(SFX_DIR / "papel_enrolando.wav", assets / "sfx_papel_enrolando.wav")
    shutil.copy2(FONTS_DIR / "Montserrat-ExtraBold.ttf", fonts_dir / "Montserrat-ExtraBold.ttf")

    dur_str = f"{duracao:.2f}"
    roll_dur = min(banner_dur, max(2.0, duracao - 0.1))
    sfx_dur = f"{min(6.0, duracao):.2f}"
    vars_json = json.dumps(
        [{"id": "gancho", "type": "string", "label": "Texto do Gancho", "default": gancho_texto}],
        ensure_ascii=False,
    )
    grupos_json = json.dumps(grupos_legenda, ensure_ascii=False)

    html = f"""<!doctype html>
<html lang="pt-BR" data-composition-variables='{vars_json.replace("'", "&#39;")}'>
<head>
  <meta charset="utf-8" />
  <title>Corte Individual — HyperFrames</title>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
  <style>
    @font-face {{
      font-family: 'MontserratClipper';
      src: url('assets/fonts/Montserrat-ExtraBold.ttf') format('truetype');
      font-weight: 800;
      font-style: normal;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
    #root {{ position: relative; width: 1080px; height: 1920px; background: #000; overflow: hidden; }}
    .divider {{
      position: absolute; top: 767px; left: 0; width: 1080px; height: 3px;
      background: rgba(0, 0, 0, 0.78); box-shadow: 0 2px 10px rgba(0,0,0,0.7); z-index: 8; pointer-events: none;
    }}
    #paper-roll-wrap {{
      position: absolute; left: 0; top: 508px; width: 1080px; height: 520px;
      z-index: 20; pointer-events: none;
    }}
    #captions-layer {{
      position: absolute; left: 44px; top: {legenda_y}px; width: 992px;
      transform: translateY(-50%); z-index: 30;
      display: flex; flex-wrap: wrap; justify-content: center; align-items: center;
      gap: 10px 30px; text-align: center; pointer-events: none;
    }}
    .cap-word {{
      display: inline-block;
      font-family: 'MontserratClipper', 'Montserrat', sans-serif;
      font-size: 62px; font-weight: 800; line-height: 1.06;
      text-transform: uppercase; letter-spacing: 0.02em; white-space: nowrap;
      color: #FFFFFF; -webkit-text-stroke: 10px #000000; paint-order: stroke fill;
      text-shadow: 0 5px 11px rgba(0,0,0,0.88);
    }}
    .cap-word.active {{
      color: #FFE500; transform: scale(1.16);
      -webkit-text-stroke: 12px #000000;
      text-shadow: 0 6px 14px rgba(0,0,0,0.94);
    }}
  </style>
</head>
<body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{dur_str}" data-width="1080" data-height="1920">
    <video id="clip-video" class="clip" src="assets/video_split.mp4" data-start="0" data-duration="{dur_str}" data-track-index="1" data-has-audio="true" playsinline style="position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:contain;z-index:1;"></video>
    <audio id="sfx-paper-roll" class="clip" src="assets/sfx_papel_enrolando.wav" data-start="0" data-duration="{sfx_dur}" data-track-index="2" data-volume="0.45"></audio>
    <div class="divider"></div>
    <div id="paper-roll-wrap" class="clip" data-start="0" data-duration="{roll_dur:.2f}" data-layout-allow-overflow>
      <canvas id="paper-roll-canvas" width="1080" height="520" style="width:1080px;height:520px;"></canvas>
    </div>
    <div id="captions-layer" class="clip" data-start="0" data-duration="{dur_str}" data-track-kind="captions" data-layout-allow-caption-zone data-layout-allow-safe-zone data-layout-allow-overflow></div>
  </div>
  <script>
    {PAPER_ROLL_CORE_JS}
    {CAPTIONS_RENDER_JS}
    const CAPTION_GROUPS = {grupos_json};
    const roll = createPaperRollRenderer('paper-roll-canvas', 'assets/banner_gancho.png', {roll_dur:.2f});
    window.addEventListener('hf-seek', (e) => {{
      if (!roll.isReady() && e.detail && typeof e.detail.waitUntil === 'function') e.detail.waitUntil(roll.loadPromise);
      const t = (e.detail && e.detail.time) || 0;
      roll.renderAt(t);
      renderCaptionsAt(CAPTION_GROUPS, 'captions-layer', t);
    }});
    const tl = gsap.timeline({{ paused: true }});
    const proxy = {{ t: 0 }};
    tl.to(proxy, {{
      t: {dur_str},
      duration: {dur_str},
      ease: 'none',
      onUpdate: () => {{
        roll.renderAt(proxy.t);
        renderCaptionsAt(CAPTION_GROUPS, 'captions-layer', proxy.t);
      }},
    }}, 0);
    renderCaptionsAt(CAPTION_GROUPS, 'captions-layer', 0);
    window.__timelines = window.__timelines || {{}};
    window.__timelines['main'] = tl;
  </script>
</body>
</html>
"""
    index_path = projeto_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


def gerar_projeto_hf_top(
    projeto_dir: Path,
    itens_processados: list[dict],
    top_title: str = "TOP REAÇÕES",
    top_subtitle: str = "",
    bottom_px: int = 240,
    gradient_opacity: float = 0.85,
    hero_sec: float = 3.0,
) -> Path:
    assets = projeto_dir / "assets"
    fonts_dir = assets / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SFX_DIR / "transicao.wav", assets / "sfx_transicao.wav")
    shutil.copy2(FONTS_DIR / "Montserrat-ExtraBold.ttf", fonts_dir / "Montserrat-ExtraBold.ttf")

    overlap = 0.20
    cursor = 0.0
    timeline_entries: list[dict] = []
    video_tags: list[str] = []
    sfx_tags: list[str] = []
    all_captions: list[dict] = []

    for idx, item in enumerate(itens_processados):
        clip_name = f"clip_rank_{item['rank']}.mp4"
        shutil.copy2(item["video_split"], assets / clip_name)
        dur = float(item["duration"])
        start = round(cursor, 3)
        end = round(cursor + dur, 3)
        track = 1 if (idx % 2 == 0) else 2
        z = idx + 1
        fade_in = ' data-fade-in="0.15"' if idx > 0 else ""
        fade_out = ' data-fade-out="0.15"' if idx < len(itens_processados) - 1 else ""
        video_tags.append(
            f'<video id="clip-rank-{item["rank"]}" class="clip" src="assets/{clip_name}" '
            f'data-start="{start:.2f}" data-duration="{dur:.2f}" data-track-index="{track}" '
            f'data-has-audio="true"{fade_in}{fade_out} playsinline '
            f'style="position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:contain;z-index:{z};"></video>'
        )
        if idx > 0:
            sfx_start = max(0.0, start - 0.05)
            sfx_tags.append(
                f'<audio id="sfx-trans-{idx}" class="clip" src="assets/sfx_transicao.wav" '
                f'data-start="{sfx_start:.2f}" data-duration="0.26" data-track-index="3" data-volume="0.36"></audio>'
            )
        timeline_entries.append(
            {
                "rank": int(item["rank"]),
                "name": item["name"],
                "start": start,
                "end": round(end - (overlap if idx < len(itens_processados) - 1 else 0.0), 3),
            }
        )
        for grp in item["captions"]:
            all_captions.append(
                {
                    "start": round(start + grp["start"], 3),
                    "end": round(start + grp["end"], 3),
                    "words": [
                        {
                            "text": w["text"],
                            "start": round(start + w["start"], 3),
                            "end": round(start + w["end"], 3),
                        }
                        for w in grp["words"]
                    ],
                }
            )
        cursor = end - overlap if idx < len(itens_processados) - 1 else end

    total_dur = max(1.0, cursor)
    dur_str = f"{total_dur:.2f}"

    nomes_1_a_n = sorted(itens_processados, key=lambda x: int(x["rank"]))
    rows_html = []
    for item in nomes_1_a_n:
        r = int(item["rank"])
        nome = item["name"].replace("<", "&lt;").replace(">", "&gt;")
        rows_html.append(
            f'''<div class="rank-row" id="rank-row-{r}" data-rank="{r}">
  <div class="rank-badge" id="rank-badge-{r}" data-layout-allow-safe-zone data-layout-ignore>{r}</div>
  <div class="rank-locked" id="rank-lock-{r}">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.6)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
    <div class="rank-bar"></div>
  </div>
  <span class="rank-name" id="rank-name-{r}" style="display:none;" data-layout-allow-safe-zone data-layout-ignore>{nome}</span>
</div>'''
        )

    subtitle_html = (
        f'<span class="top-subtitle" data-layout-allow-safe-zone data-layout-ignore>{top_subtitle.upper()}</span>'
        if top_subtitle.strip()
        else ""
    )
    timeline_json = json.dumps(timeline_entries, ensure_ascii=False)
    captions_json = json.dumps(all_captions, ensure_ascii=False)

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>{top_title} — HyperFrames</title>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
  <style>
    @font-face {{
      font-family: 'MontserratClipper';
      src: url('assets/fonts/Montserrat-ExtraBold.ttf') format('truetype');
      font-weight: 800; font-style: normal;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
    #root {{ position: relative; width: 1080px; height: 1920px; background: #000; overflow: hidden; }}
    .divider {{
      position: absolute; top: 767px; left: 0; width: 1080px; height: 3px;
      background: rgba(0,0,0,0.78); box-shadow: 0 2px 10px rgba(0,0,0,0.7); z-index: 10; pointer-events: none;
    }}
    #top-gradient {{
      position: absolute; top: 768px; left: 0; width: 1080px; height: 1152px; z-index: 15; pointer-events: none;
      opacity: {gradient_opacity:.2f};
      background-image: radial-gradient(ellipse 95% 76% at 0% 100%, rgba(0,0,0,0.84) 0%, rgba(0,0,0,0.52) 48%, rgba(0,0,0,0) 100%),
                        linear-gradient(to top, rgba(0,0,0,0.58) 0%, rgba(0,0,0,0.22) 28%, rgba(0,0,0,0) 56%);
    }}
    #top-ranking {{
      position: absolute; left: 40px; bottom: {bottom_px}px; z-index: 25;
      display: flex; flex-direction: column; align-items: flex-start; gap: 10px; pointer-events: none;
    }}
    #top-header {{
      display: flex; align-items: stretch; gap: 16px; padding-left: 6px; margin-bottom: 4px;
      transform-origin: left bottom;
    }}
    .top-bar {{ width: 9px; border-radius: 5px; background: #FFE500; box-shadow: 0 0 18px rgba(255,229,0,0.55); flex-shrink: 0; }}
    .top-titles {{ display: flex; flex-direction: column; gap: 4px; }}
    .top-title {{
      font-family: 'MontserratClipper', sans-serif; font-size: 68px; font-weight: 800; line-height: 0.98;
      letter-spacing: 0.02em; text-transform: uppercase; color: #FFE500;
      -webkit-text-stroke: 10px #000; paint-order: stroke fill; text-shadow: 0 8px 20px rgba(0,0,0,0.95); white-space: nowrap;
    }}
    .top-subtitle {{
      font-family: 'MontserratClipper', sans-serif; font-size: 44px; font-weight: 800; line-height: 1.05;
      letter-spacing: 0.025em; text-transform: uppercase; color: #FFFFFF;
      -webkit-text-stroke: 8px #000; paint-order: stroke fill; text-shadow: 0 6px 16px rgba(0,0,0,0.95); white-space: nowrap;
    }}
    .rank-row {{
      display: flex; align-items: center; gap: 14px; border-left: 4px solid transparent;
      border-radius: 12px; padding: 3px 12px; width: fit-content;
    }}
    .rank-row.active {{
      background: rgba(0,0,0,0.48); border-left-color: #FFE500; padding: 6px 20px 6px 12px;
    }}
    .rank-badge {{
      width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
      font-family: 'MontserratClipper', sans-serif; font-size: 25px; font-weight: 800; flex-shrink: 0;
      background: rgba(0,0,0,0.56); border: 1.5px solid rgba(255,255,255,0.24); color: rgba(255,255,255,0.65);
      box-shadow: 0 3px 10px rgba(0,0,0,0.55);
    }}
    .rank-row.revealed .rank-badge {{
      background: rgba(0,0,0,0.62); border-color: rgba(255,255,255,0.36); color: #FFFFFF;
    }}
    .rank-row.active .rank-badge {{
      width: 48px; height: 48px; border-radius: 11px; font-size: 28px;
      background: #FFE500; border-color: #FFE500; color: #090909; box-shadow: 0 4px 18px rgba(255,229,0,0.42);
    }}
    .rank-locked {{
      display: flex; align-items: center; gap: 10px; padding: 10px 16px; border-radius: 10px;
      background: rgba(0,0,0,0.36); border: 1px solid rgba(255,255,255,0.14);
    }}
    .rank-bar {{ width: 145px; height: 12px; border-radius: 6px; background: rgba(255,255,255,0.18); }}
    .rank-name {{
      font-family: 'MontserratClipper', sans-serif; font-size: 40px; font-weight: 800; line-height: 1.08;
      color: #FFFFFF; opacity: 0.94; -webkit-text-stroke: 5px #000; paint-order: stroke fill;
      text-shadow: 0 4px 12px rgba(0,0,0,0.95); white-space: nowrap;
    }}
    .rank-row.active .rank-name {{ font-size: 44px; color: #FFE500; opacity: 1; -webkit-text-stroke: 6px #000; }}
    #captions-layer {{
      position: absolute; top: 768px; left: 44px; width: 992px; transform: translateY(-50%); z-index: 30;
      display: flex; flex-wrap: wrap; justify-content: center; align-items: center;
      gap: 10px 34px; text-align: center; pointer-events: none;
    }}
    .cap-word {{
      display: inline-block; font-family: 'MontserratClipper', sans-serif; font-size: 58px; font-weight: 800;
      line-height: 1.06; text-transform: uppercase; letter-spacing: 0.02em; white-space: nowrap;
      color: #FFFFFF; -webkit-text-stroke: 10px #000; paint-order: stroke fill; text-shadow: 0 5px 11px rgba(0,0,0,0.88);
    }}
    .cap-word.active {{
      color: #FFE500; transform: scale(1.15); -webkit-text-stroke: 12px #000; text-shadow: 0 6px 14px rgba(0,0,0,0.94);
    }}
  </style>
</head>
<body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{dur_str}" data-width="1080" data-height="1920">
    {''.join(video_tags)}
    {''.join(sfx_tags)}
    <div class="divider"></div>
    <div id="top-gradient" data-layout-ignore></div>
    <div id="top-ranking" class="clip" data-start="0" data-duration="{dur_str}" data-layout-allow-overflow data-layout-allow-caption-zone data-layout-allow-safe-zone>
      <div id="top-header">
        <div class="top-bar"></div>
        <div class="top-titles">
          <span class="top-title" data-layout-allow-safe-zone data-layout-ignore>{top_title.upper()}</span>
          {subtitle_html}
        </div>
      </div>
      {''.join(rows_html)}
    </div>
    <div id="captions-layer" class="clip" data-start="0" data-duration="{dur_str}" data-track-kind="captions" data-layout-allow-overflow></div>
  </div>
  <script>
    {CAPTIONS_RENDER_JS}
    const TOP_TIMELINE = {timeline_json};
    const ALL_CAPTIONS = {captions_json};
    const HERO_SEC = {hero_sec:.2f};

    function updateTopOverlay(t) {{
      const header = document.getElementById('top-header');
      if (header) {{
        const s = t <= 0.25 ? 0.9 + 0.1 * (t / 0.25)
          : t <= HERO_SEC ? 1.0
          : t <= HERO_SEC + 0.47 ? 1.0 - 0.44 * ((t - HERO_SEC) / 0.47)
          : 0.56;
        header.style.transform = `scale(${{s.toFixed(3)}})`;
      }}
      const activeEntry = TOP_TIMELINE.find(e => t >= e.start && t < e.end) || TOP_TIMELINE[TOP_TIMELINE.length - 1];
      const activeRank = activeEntry ? activeEntry.rank : -1;
      for (const entry of TOP_TIMELINE) {{
        const row = document.getElementById('rank-row-' + entry.rank);
        const lockEl = document.getElementById('rank-lock-' + entry.rank);
        const nameEl = document.getElementById('rank-name-' + entry.rank);
        if (!row) continue;
        const revealed = t >= entry.start;
        const isActive = revealed && entry.rank === activeRank;
        row.classList.toggle('revealed', revealed);
        row.classList.toggle('active', isActive);
        if (lockEl) lockEl.style.display = revealed ? 'none' : 'flex';
        if (nameEl) nameEl.style.display = revealed ? 'inline' : 'none';
      }}
    }}
    window.addEventListener('hf-seek', (e) => {{
      const t = (e.detail && e.detail.time) || 0;
      renderCaptionsAt(ALL_CAPTIONS, 'captions-layer', t);
      updateTopOverlay(t);
    }});
    const tl = gsap.timeline({{ paused: true }});
    const proxy = {{ t: 0 }};
    tl.to(proxy, {{
      t: {dur_str},
      duration: {dur_str},
      ease: 'none',
      onUpdate: () => {{
        renderCaptionsAt(ALL_CAPTIONS, 'captions-layer', proxy.t);
        updateTopOverlay(proxy.t);
      }},
    }}, 0);
    renderCaptionsAt(ALL_CAPTIONS, 'captions-layer', 0);
    updateTopOverlay(0);
    window.__timelines = window.__timelines || {{}};
    window.__timelines['main'] = tl;
  </script>
</body>
</html>
"""
    index_path = projeto_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


def cmd_batch(args: argparse.Namespace) -> None:
    if args.md:
        dados = parse_repurpose_md(Path(args.md))
        fonte = args.fonte or dados["fonte"]
        momentos = dados["momentos"]
        if args.cortes and args.cortes.lower() != "all":
            alvos = {x.strip() for x in args.cortes.split(",") if x.strip()}
            momentos = [m for m in momentos if str(m["numero"]) in alvos or m["slug"] in alvos]
    else:
        if not args.fonte or args.inicio is None or args.fim is None:
            raise SystemExit("Informe --md OU (--fonte, --inicio e --fim).")
        momentos = [
            {
                "numero": 1,
                "slug": args.slug or "corte-01",
                "inicio_s": hms_para_segundos(args.inicio),
                "fim_s": hms_para_segundos(args.fim),
                "gancho": args.gancho or "OLHA O QUE *ACONTECEU*",
                "por_que_funciona": args.resumo or "",
            }
        ]
        fonte = args.fonte

    saida_raiz = Path(args.saida_dir).resolve()
    work_dir = saida_raiz / "_tmp"
    work_dir.mkdir(parents=True, exist_ok=True)

    resumo_out = []
    for m in momentos:
        slug = m["slug"]
        gancho = args.gancho if (args.gancho and len(momentos) == 1) else m["gancho"]
        bruto = work_dir / f"{slug}_raw.mp4"
        split = work_dir / f"{slug}_split.mp4"
        banner_png = work_dir / f"{slug}_banner.png"
        proj_dir = saida_raiz / f"hf_{slug}"

        baixar_ou_recortar_trecho(fonte, m["inicio_s"], m["fim_s"], bruto)
        com_cam, dur_real = gerar_split_vertical(bruto, split, facecam_mode=args.facecam, cam_h=768)
        palavras = transcrever_palavras(split, idioma=args.idioma, modelo=args.whisper_modelo)
        grupos = agrupar_legendas(palavras, dur_real)
        gerar_png_banner_enrolando(gancho, banner_png)
        index_html = gerar_projeto_hf_individual(
            proj_dir, split, banner_png, dur_real, grupos, gancho.replace("*", ""), legenda_y=args.legenda_y
        )
        resumo_out.append(
            {
                "slug": slug,
                "projeto_hyperframes": str(proj_dir),
                "index_html": str(index_html),
                "duracao_s": round(dur_real, 2),
                "facecam": com_cam,
                "palavras": len(palavras),
                "gancho": gancho,
                "fonte": fonte,
            }
        )

    if args.limpar_tmp:
        shutil.rmtree(work_dir, ignore_errors=True)
    print(json.dumps(resumo_out, ensure_ascii=False, indent=2))


def cmd_batch_top(args: argparse.Namespace) -> None:
    cfg = json.loads(Path(args.top_json).read_text(encoding="utf-8"))
    itens = cfg["itens"]
    saida_raiz = Path(args.saida_dir).resolve()
    work_dir = saida_raiz / "_tmp_top"
    work_dir.mkdir(parents=True, exist_ok=True)

    processados = []
    for it in itens:
        rank = int(it["rank"])
        bruto = work_dir / f"raw_{rank}.mp4"
        split = work_dir / f"split_{rank}.mp4"
        s = hms_para_segundos(it["inicio"])
        e = hms_para_segundos(it["fim"])
        baixar_ou_recortar_trecho(it["fonte"], s, e, bruto)
        _, dur_real = gerar_split_vertical(bruto, split, facecam_mode=it.get("facecam", "auto"), cam_h=768)
        palavras = transcrever_palavras(split, idioma=args.idioma, modelo=args.whisper_modelo)
        grupos = agrupar_legendas(palavras, dur_real)
        processados.append(
            {
                "rank": rank,
                "name": it["nome"],
                "video_split": split,
                "duration": dur_real,
                "captions": grupos,
            }
        )

    proj_dir = saida_raiz / (cfg.get("slug") or "hf_top")
    index_html = gerar_projeto_hf_top(
        proj_dir,
        processados,
        top_title=cfg.get("titulo", "TOP REAÇÕES"),
        top_subtitle=cfg.get("subtitulo", ""),
        bottom_px=int(cfg.get("bottomPx", 240)),
        gradient_opacity=float(cfg.get("gradientOpacity", 0.85)),
        hero_sec=float(cfg.get("heroSec", 3.0)),
    )
    if args.limpar_tmp:
        shutil.rmtree(work_dir, ignore_errors=True)
    print(
        json.dumps(
            {"projeto_hyperframes": str(proj_dir), "index_html": str(index_html), "itens": len(processados)},
            ensure_ascii=False,
            indent=2,
        )
    )


# =====================================================================
# 7. Modo 2 — Padrao Hibrido Narrativo (Geracao 2 — Estilo Corvette)
# =====================================================================
COLOR_GRADE_DISSOLVE = json.dumps(
    {
        "preset": None,
        "intensity": 1,
        "adjust": {
            "exposure": -0.45,
            "contrast": 0.22,
            "highlights": 0,
            "shadows": 0,
            "whites": 0,
            "blacks": 0,
            "temperature": 0,
            "tint": 0,
            "vibrance": 0,
            "saturation": -0.55,
        },
        "details": {"vignette": 0.42, "vignetteMidpoint": 0.5, "vignetteRoundness": 0, "vignetteFeather": 0.65, "grain": 0, "grainSize": 0.25, "grainRoughness": 0.5},
        "effects": {"blur": 0, "pixelate": 0, "chromaBleed": 0, "tapeDamage": 0, "tapeTracking": 0, "tapeNoise": 1, "tapeSpeed": 0.5, "filmArtifacts": 0, "halftone": 0, "halftoneSize": 0, "twoInkPrint": 0, "twoInkPrintSize": 0, "ascii": 0, "asciiSize": 0.06578947368421052, "asciiInvert": 0, "asciiStyle": 0, "asciiColor": 1, "asciiRotation": 0, "dither": 0, "ditherSize": 0, "bloom": 0, "bloomRadius": 8, "monoScreen": 0, "monoScreenSize": 0, "monoScreenAngle": 0, "monoScreenSpread": 0, "monoScreenShape": 0, "monoScreenInvert": 0, "scanlines": 0, "scanlineCount": 0, "scanlineSoftness": 0, "chromaticAberration": 0, "chromaticAngle": 0, "crtCurvature": 0, "digitalGlitch": 0, "digitalGlitchColorSplit": 0, "digitalGlitchLineTear": 0, "digitalGlitchPixelate": 0, "digitalGlitchBlockAmount": 0, "digitalGlitchBlockDisplacement": 0, "digitalGlitchBlockOpacity": 0, "digitalGlitchSpeed": 0, "engraving": 0, "engravingSpacing": 0.4117647058823529, "engravingMinThickness": 0.2, "engravingMaxThickness": 0.4571428571428572, "engravingAngle": 0.25, "engravingContrast": 0.4666666666666667, "engravingSharpness": 0.59, "engravingWave": 0.2, "engravingWaveFrequency": 0.2222222222222222, "crosshatch": 0, "crosshatchSpacing": 0.28, "crosshatchThickness": 0.25, "crosshatchAngle": 0.25, "crosshatchContrast": 0.3333333333333333, "crosshatchEdges": 0.5, "crosshatchLineWeight": 0, "crosshatchWave": 0.33, "crosshatchWaveFrequency": 0.2222222222222222, "kuwahara": 0, "kuwaharaRadius": 0.14285714285714285, "kuwaharaSharpness": 0.3125, "kuwaharaSaturation": 0.5},
        "lut": None,
        "colorSpace": "rec709",
    }
)

COLOR_GRADE_CRIMSON_END = json.dumps(
    {
        "preset": None,
        "intensity": 1,
        "adjust": {
            "exposure": -0.18,
            "contrast": 0.35,
            "highlights": 0,
            "shadows": 0,
            "whites": 0,
            "blacks": 0,
            "temperature": 0.62,
            "tint": 0.72,
            "vibrance": 0,
            "saturation": -0.25,
        },
        "details": {"vignette": 0.48, "vignetteMidpoint": 0.5, "vignetteRoundness": 0, "vignetteFeather": 0.65, "grain": 0, "grainSize": 0.25, "grainRoughness": 0.5},
        "effects": {"blur": 0, "pixelate": 0, "chromaBleed": 0, "tapeDamage": 0, "tapeTracking": 0, "tapeNoise": 1, "tapeSpeed": 0.5, "filmArtifacts": 0, "halftone": 0, "halftoneSize": 0, "twoInkPrint": 0, "twoInkPrintSize": 0, "ascii": 0, "asciiSize": 0.06578947368421052, "asciiInvert": 0, "asciiStyle": 0, "asciiColor": 1, "asciiRotation": 0, "dither": 0, "ditherSize": 0, "bloom": 0, "bloomRadius": 8, "monoScreen": 0, "monoScreenSize": 0, "monoScreenAngle": 0, "monoScreenSpread": 0, "monoScreenShape": 0, "monoScreenInvert": 0, "scanlines": 0, "scanlineCount": 0, "scanlineSoftness": 0, "chromaticAberration": 0, "chromaticAngle": 0, "crtCurvature": 0, "digitalGlitch": 0, "digitalGlitchColorSplit": 0, "digitalGlitchLineTear": 0, "digitalGlitchPixelate": 0, "digitalGlitchBlockAmount": 0, "digitalGlitchBlockDisplacement": 0, "digitalGlitchBlockOpacity": 0, "digitalGlitchSpeed": 0, "engraving": 0, "engravingSpacing": 0.4117647058823529, "engravingMinThickness": 0.2, "engravingMaxThickness": 0.4571428571428572, "engravingAngle": 0.25, "engravingContrast": 0.4666666666666667, "engravingSharpness": 0.59, "engravingWave": 0.2, "engravingWaveFrequency": 0.2222222222222222, "crosshatch": 0, "crosshatchSpacing": 0.28, "crosshatchThickness": 0.25, "crosshatchAngle": 0.25, "crosshatchContrast": 0.3333333333333333, "crosshatchEdges": 0.5, "crosshatchLineWeight": 0, "crosshatchWave": 0.33, "crosshatchWaveFrequency": 0.2222222222222222, "kuwahara": 0, "kuwaharaRadius": 0.14285714285714285, "kuwaharaSharpness": 0.3125, "kuwaharaSaturation": 0.5},
        "lut": None,
        "colorSpace": "rec709",
    }
)


def _escrever_subcomposicoes_hibrido(
    comps_dir: Path,
    *,
    cam_h: int,
    game_h: int,
    hook_cfg: dict,
    rewind_cfg: dict | None,
    promise_cfg: dict | None,
    hud_cfg: dict | None,
    dissolve_cfg: dict | None,
    ending_cfg: dict | None,
    captions_groups: list[dict],
    captions_dur: float,
    captions_y: int,
) -> list[str]:
    comps_dir.mkdir(parents=True, exist_ok=True)
    montadas: list[str] = []

    # 1. Hook Banner (Unico no Cold Open)
    hb_dur = float(hook_cfg.get("duration", 3.88))
    hb_top = int(hook_cfg.get("top", max(320, cam_h - 170)))
    (comps_dir / "hook-banner.html").write_text(
        f"""<template>
  <style>
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    #paper-roll-wrap {{
      position: absolute; left: 0; top: {hb_top}px; width: 1080px; height: 520px; pointer-events: none;
    }}
  </style>
  <div id="root" data-composition-id="hook-banner" data-width="1080" data-height="1920">
    <div id="paper-roll-wrap" class="clip" data-start="0" data-duration="{hb_dur:.2f}" data-layout-allow-overflow>
      <canvas id="paper-roll-canvas" width="1080" height="520" style="width:1080px;height:520px;"></canvas>
    </div>
  </div>
  <script>
    (function () {{
      {PAPER_ROLL_CORE_JS}
      const roll = createPaperRollRenderer('paper-roll-canvas', 'assets/banner_gancho.png', {hb_dur:.2f});
      const tl = gsap.timeline({{ paused: true }});
      const proxy = {{ t: 0 }};
      tl.to(proxy, {{
        t: {hb_dur:.2f},
        duration: {hb_dur:.2f},
        ease: 'none',
        onUpdate: () => roll.renderAt(proxy.t),
      }}, 0);
      window.addEventListener('hf-seek', (e) => {{
        if (!roll.isReady() && e.detail && typeof e.detail.waitUntil === 'function') e.detail.waitUntil(roll.loadPromise);
      }});
      window.__timelines = window.__timelines || {{}};
      window.__timelines['hook-banner'] = tl;
    }})();
  </script>
</template>
""",
        encoding="utf-8",
    )
    montadas.append(
        f'<div id="hook-banner" data-composition-id="hook-banner" data-composition-src="compositions/hook-banner.html" '
        f'data-start="0.00" data-duration="{hb_dur:.2f}" data-track-index="2" data-track-kind="graphics" '
        f'data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:16;"></div>'
    )

    # 2. Rewind Badge ("VOLTANDO NO TEMPO")
    if rewind_cfg:
        rw_start = float(rewind_cfg["start"])
        rw_dur = float(rewind_cfg.get("duration", 1.85))
        rw_label = str(rewind_cfg.get("label", "VOLTANDO NO TEMPO"))
        rw_top = int(rewind_cfg.get("top", cam_h + 28))
        (comps_dir / "rewind-badge.html").write_text(
            f"""<template>
  <style>
    @font-face {{
      font-family: 'MontserratClipper';
      src: url('assets/fonts/Montserrat-ExtraBold.ttf') format('truetype');
      font-weight: 800; font-style: normal;
    }}
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    #rewind-flash {{ position: absolute; inset: 0; background: #FFFFFF; opacity: 0; }}
    #rewind-pill-wrap {{
      position: absolute; left: 120px; top: {rw_top}px; width: 768px; display: flex; justify-content: center;
    }}
    #rewind-pill {{
      display: inline-flex; align-items: center; gap: 12px; padding: 12px 26px; border-radius: 999px;
      background: rgba(11, 9, 20, 0.88); border: 3px solid #FFE500; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.72);
      font-family: 'MontserratClipper', sans-serif; font-size: 30px; font-weight: 800; letter-spacing: 0.04em;
      color: #FFFFFF; text-transform: uppercase;
    }}
    #rewind-pill .tri {{ color: #FFE500; font-size: 32px; }}
  </style>
  <div id="root" data-composition-id="rewind-badge" data-width="1080" data-height="1920">
    <div id="rewind-flash" class="clip" data-start="0" data-duration="0.18"></div>
    <div id="rewind-pill-wrap" class="clip" data-start="0.06" data-duration="{max(0.4, rw_dur - 0.15):.2f}" data-layout-allow-safe-zone>
      <div id="rewind-pill">
        <span class="tri">&#9664;&#9664;</span>
        <span>{rw_label}</span>
      </div>
    </div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo('#rewind-flash', {{ opacity: 0.85 }}, {{ opacity: 0, duration: 0.16, ease: 'power2.out' }}, 0);
    tl.fromTo('#rewind-pill', {{ opacity: 0, y: -14, scale: 0.9 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.24, ease: 'power3.out' }}, 0.06);
    tl.to('#rewind-pill', {{ opacity: 0, y: -10, duration: 0.20, ease: 'power2.in' }}, {max(0.35, rw_dur - 0.35):.2f});
    window.__timelines = window.__timelines || {{}};
    window.__timelines['rewind-badge'] = tl;
  </script>
</template>
""",
            encoding="utf-8",
        )
        montadas.append(
            f'<div id="rewind-badge" data-composition-id="rewind-badge" data-composition-src="compositions/rewind-badge.html" '
            f'data-start="{rw_start:.2f}" data-duration="{rw_dur:.2f}" data-track-index="2" data-track-kind="graphics" '
            f'data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:16;"></div>'
        )

    # 3. Promise Goal ("OBJETIVO: ...")
    if promise_cfg:
        pr_start = float(promise_cfg["start"])
        pr_dur = float(promise_cfg.get("duration", 3.25))
        pr_kicker = str(promise_cfg.get("kicker", "OBJETIVO:"))
        pr_label = str(promise_cfg.get("label", "CUMPRIR A MISSÃO!"))
        pr_top = int(promise_cfg.get("top", cam_h + 36))
        (comps_dir / "promise-goal.html").write_text(
            f"""<template>
  <style>
    @font-face {{
      font-family: 'MontserratClipper';
      src: url('assets/fonts/Montserrat-ExtraBold.ttf') format('truetype');
      font-weight: 800; font-style: normal;
    }}
    @font-face {{
      font-family: 'AntonClipper';
      src: url('assets/fonts/Anton-Regular.ttf') format('truetype');
      font-weight: 400; font-style: normal;
    }}
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    #promise-box {{
      position: absolute; left: 120px; top: {pr_top}px; width: 768px;
      display: flex; flex-direction: column; align-items: center; text-align: center; gap: 4px;
    }}
    .goal-kicker {{
      font-family: 'MontserratClipper', sans-serif; font-size: 46px; font-weight: 800; letter-spacing: 0.05em;
      color: #FFFFFF; -webkit-text-stroke: 8px #000000; paint-order: stroke fill;
      text-shadow: 0 5px 14px rgba(0, 0, 0, 0.9); text-transform: uppercase;
    }}
    .goal-main {{
      font-family: 'AntonClipper', 'MontserratClipper', sans-serif; font-size: 80px; line-height: 1.02;
      letter-spacing: 0.02em; color: #2BFF66; -webkit-text-stroke: 10px #090909; paint-order: stroke fill;
      text-shadow: 0 8px 20px rgba(0, 0, 0, 0.95); text-transform: uppercase;
    }}
  </style>
  <div id="root" data-composition-id="promise-goal" data-width="1080" data-height="1920">
    <div id="promise-box" class="clip" data-start="0" data-duration="{max(0.5, pr_dur - 0.05):.2f}" data-layout-allow-safe-zone>
      <div id="promise-inner">
        <div class="goal-kicker">{pr_kicker}</div>
        <div class="goal-main" data-var-text="goal-label">{pr_label}</div>
      </div>
    </div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo('#promise-inner', {{ opacity: 0, scale: 1.18, y: 10 }}, {{ opacity: 1, scale: 1.0, y: 0, duration: 0.24, ease: 'power4.out' }}, 0);
    tl.to('#promise-inner', {{ opacity: 0, scale: 0.94, duration: 0.20, ease: 'power2.in' }}, {max(0.4, pr_dur - 0.30):.2f});
    window.__timelines = window.__timelines || {{}};
    window.__timelines['promise-goal'] = tl;
  </script>
</template>
""",
            encoding="utf-8",
        )
        montadas.append(
            f'<div id="promise-goal" data-composition-id="promise-goal" data-composition-src="compositions/promise-goal.html" '
            f'data-start="{pr_start:.2f}" data-duration="{pr_dur:.2f}" data-track-index="2" data-track-kind="graphics" '
            f'data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:16;"></div>'
        )

    # 4. HUD Callout Card
    if hud_cfg:
        hc_start = float(hud_cfg["start"])
        hc_dur = float(hud_cfg.get("duration", 4.50))
        hc_top_txt = str(hud_cfg.get("top_label", "DETALHE:"))
        hc_bot_txt = str(hud_cfg.get("bottom_label", "OLHA ISSO!"))
        hc_top_y = int(hud_cfg.get("top", cam_h + 32))
        (comps_dir / "hud-callout.html").write_text(
            f"""<template>
  <style>
    @font-face {{
      font-family: 'MontserratClipper';
      src: url('assets/fonts/Montserrat-ExtraBold.ttf') format('truetype');
      font-weight: 800; font-style: normal;
    }}
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    #hud-card-wrap {{
      position: absolute; left: 120px; top: {hc_top_y}px; width: 768px; display: flex; justify-content: flex-end;
    }}
    #hud-card {{
      display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 14px 16px;
      border-radius: 18px; background: rgba(12, 10, 18, 0.90); border: 3px solid #E51A2E;
      box-shadow: 0 12px 28px rgba(0, 0, 0, 0.85);
    }}
    #hud-card img {{ width: 310px; height: auto; border-radius: 10px; display: block; }}
    .hud-tag {{
      font-family: 'MontserratClipper', sans-serif; font-size: 32px; font-weight: 800; color: #FFE500;
      letter-spacing: 0.02em; text-transform: uppercase; -webkit-text-stroke: 5px #000000;
      paint-order: stroke fill; text-align: center;
    }}
    .hud-sub {{
      font-family: 'MontserratClipper', sans-serif; font-size: 28px; font-weight: 800; color: #FFFFFF;
      text-transform: uppercase; text-align: center;
    }}
  </style>
  <div id="root" data-composition-id="hud-callout" data-width="1080" data-height="1920">
    <div id="hud-card-wrap" class="clip" data-start="0" data-duration="{hc_dur:.2f}" data-layout-allow-safe-zone>
      <div id="hud-card">
        <div class="hud-sub">{hc_top_txt}</div>
        <img src="assets/hud_callout.png" alt="Recorte ampliado do HUD" />
        <div class="hud-tag">{hc_bot_txt}</div>
      </div>
    </div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo('#hud-card', {{ opacity: 0, x: 40, scale: 0.92 }}, {{ opacity: 1, x: 0, scale: 1, duration: 0.28, ease: 'power3.out' }}, 0);
    tl.to('#hud-card', {{ opacity: 0, x: 24, duration: 0.22, ease: 'power2.in' }}, {max(0.4, hc_dur - 0.26):.2f});
    window.__timelines = window.__timelines || {{}};
    window.__timelines['hud-callout'] = tl;
  </script>
</template>
""",
            encoding="utf-8",
        )
        montadas.append(
            f'<div id="hud-callout" data-composition-id="hud-callout" data-composition-src="compositions/hud-callout.html" '
            f'data-start="{hc_start:.2f}" data-duration="{hc_dur:.2f}" data-track-index="2" data-track-kind="graphics" '
            f'data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:16;"></div>'
        )

    # 5. Joke Dissolve Overlay
    if dissolve_cfg:
        jd_start = float(dissolve_cfg["start"])
        jd_dur = float(dissolve_cfg.get("duration", 5.00))
        jd_label = str(dissolve_cfg.get("label", "*SEM SAÍDA*"))
        jd_opacity = float(dissolve_cfg.get("face_opacity", 0.54))
        (comps_dir / "joke-dissolve.html").write_text(
            f"""<template>
  <style>
    @font-face {{
      font-family: 'MontserratClipper';
      src: url('assets/fonts/Montserrat-ExtraBold.ttf') format('truetype');
      font-weight: 800; font-style: normal;
    }}
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    #dissolve-face-vid {{
      position: absolute; left: 0; top: 120px; width: 1080px; height: 760px; object-fit: cover;
      opacity: 0; z-index: 1;
      -webkit-mask-image: linear-gradient(to bottom, transparent 0%, black 18%, black 80%, transparent 100%);
      mask-image: linear-gradient(to bottom, transparent 0%, black 18%, black 80%, transparent 100%);
    }}
    #dissolve-label-wrap {{
      position: absolute; left: 120px; top: 860px; width: 660px; display: flex;
      justify-content: center; text-align: center; z-index: 4;
    }}
    #dissolve-label {{
      font-family: 'MontserratClipper', sans-serif; font-size: 60px; font-weight: 800; line-height: 1.08;
      text-transform: uppercase; letter-spacing: 0.03em; color: rgba(255, 255, 255, 0.22);
      -webkit-text-stroke: 4px #FFFFFF; text-shadow: 0 8px 26px rgba(0, 0, 0, 0.92);
    }}
  </style>
  <div id="root" data-composition-id="joke-dissolve" data-width="1080" data-height="1920">
    <video id="dissolve-face-vid" class="clip" src="assets/dissolve_face.mp4" data-start="0" data-duration="{jd_dur:.2f}" data-track-index="1" muted playsinline></video>
    <div id="dissolve-label-wrap" class="clip" data-start="0.22" data-duration="{max(0.4, jd_dur - 0.45):.2f}" data-layout-allow-safe-zone>
      <div id="dissolve-label" data-var-text="dissolve-label">{jd_label}</div>
    </div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo('#dissolve-face-vid', {{ opacity: 0 }}, {{ opacity: {jd_opacity:.2f}, duration: 0.32, ease: 'power2.out' }}, 0);
    tl.to('#dissolve-face-vid', {{ opacity: 0, duration: 0.30, ease: 'power2.in' }}, {max(0.5, jd_dur - 0.32):.2f});
    tl.fromTo('#dissolve-label', {{ opacity: 0, scale: 0.92 }}, {{ opacity: 1, scale: 1.0, duration: 0.25, ease: 'power3.out' }}, 0.22);
    tl.to('#dissolve-label', {{ opacity: 0, duration: 0.22, ease: 'power2.in' }}, {max(0.5, jd_dur - 0.50):.2f});
    window.__timelines = window.__timelines || {{}};
    window.__timelines['joke-dissolve'] = tl;
  </script>
</template>
""",
            encoding="utf-8",
        )
        montadas.append(
            f'<div id="joke-dissolve" data-composition-id="joke-dissolve" data-composition-src="compositions/joke-dissolve.html" '
            f'data-start="{jd_start:.2f}" data-duration="{jd_dur:.2f}" data-track-index="2" data-track-kind="graphics" '
            f'data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:15;"></div>'
        )

    # 6. Captions Sub-composition
    caps_json = json.dumps(captions_groups, ensure_ascii=False)
    (comps_dir / "captions.html").write_text(
        f"""<template>
  <style>
    @font-face {{
      font-family: 'MontserratClipper';
      src: url('assets/fonts/Montserrat-ExtraBold.ttf') format('truetype');
      font-weight: 800; font-style: normal;
    }}
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    #captions-layer {{
      position: absolute; left: 120px; top: {captions_y}px; width: 660px; transform: translateY(-50%);
      display: flex; flex-wrap: wrap; justify-content: center; align-items: center;
      gap: 10px 26px; text-align: center; pointer-events: none;
    }}
    .cap-word {{
      display: inline-block; font-family: 'MontserratClipper', sans-serif; font-size: 56px; font-weight: 800;
      line-height: 1.06; text-transform: uppercase; letter-spacing: 0.02em; white-space: nowrap;
      color: #FFFFFF; -webkit-text-stroke: 10px #000000; paint-order: stroke fill;
      text-shadow: 0 5px 11px rgba(0, 0, 0, 0.88);
    }}
    .cap-word.active {{
      color: #FFE500; transform: scale(1.14); -webkit-text-stroke: 12px #000000;
      text-shadow: 0 6px 14px rgba(0, 0, 0, 0.94);
    }}
  </style>
  <div id="root" data-composition-id="captions" data-width="1080" data-height="1920">
    <div id="captions-layer" class="clip" data-start="0" data-duration="{captions_dur:.2f}" data-layout-allow-caption-zone data-layout-allow-safe-zone></div>
  </div>
  <script>
    (function () {{
      const CAPTION_GROUPS = {caps_json};
      {CAPTIONS_RENDER_JS}
      const tl = gsap.timeline({{ paused: true }});
      const proxy = {{ t: 0 }};
      tl.to(proxy, {{
        t: {captions_dur:.2f},
        duration: {captions_dur:.2f},
        ease: 'none',
        onUpdate: () => renderCaptionsAt(CAPTION_GROUPS, 'captions-layer', proxy.t),
      }}, 0);
      renderCaptionsAt(CAPTION_GROUPS, 'captions-layer', 0);
      window.__timelines = window.__timelines || {{}};
      window.__timelines['captions'] = tl;
    }})();
  </script>
</template>
""",
        encoding="utf-8",
    )
    montadas.append(
        f'<div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" '
        f'data-start="0" data-duration="{captions_dur:.2f}" data-track-index="3" data-track-kind="captions" '
        f'data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:25;"></div>'
    )

    # 7. Abrupt GTA-style Ending
    if ending_cfg:
        ed_start = float(ending_cfg["start"])
        ed_dur = float(ending_cfg.get("duration", 1.35))
        ed_word = str(ending_cfg.get("word", "se deu mal"))
        cg_attr = COLOR_GRADE_CRIMSON_END.replace('"', "&quot;")
        (comps_dir / "abrupt-ending.html").write_text(
            f"""<template>
  <style>
    @font-face {{
      font-family: 'AntonClipper';
      src: url('assets/fonts/Anton-Regular.ttf') format('truetype');
      font-weight: 400; font-style: normal;
    }}
    #root {{ position: absolute; inset: 0; background: #000000; pointer-events: none; }}
    #end-face-wrap {{ position: absolute; left: 0; top: 0; width: 1080px; height: {cam_h}px; overflow: hidden; }}
    #end-game-wrap {{ position: absolute; left: 0; top: {cam_h}px; width: 1080px; height: {game_h}px; overflow: hidden; }}
    .end-divider {{ position: absolute; top: {cam_h - 1}px; left: 0; width: 1080px; height: 3px; background: #0B0B0F; z-index: 5; }}
    #end-flash {{
      position: absolute; inset: 0;
      background: radial-gradient(circle at 50% 62%, #FFFFFF 0%, #FFE6E6 48%, rgba(229, 26, 46, 0.85) 100%);
      opacity: 0; z-index: 10;
    }}
    #end-word-wrap {{
      position: absolute; left: 120px; top: 940px; width: 768px; display: flex;
      justify-content: center; text-align: center; z-index: 12;
    }}
    #end-word {{
      font-family: 'AntonClipper', sans-serif; font-size: 134px; line-height: 0.96; letter-spacing: 0.02em;
      color: #FFFFFF; -webkit-text-stroke: 12px #090909; paint-order: stroke fill;
      text-shadow: 0 12px 30px rgba(0, 0, 0, 0.95);
    }}
  </style>
  <div id="root" data-composition-id="abrupt-ending" data-width="1080" data-height="1920">
    <div id="end-face-wrap">
      <img id="end-face-img" src="assets/final_face_freeze.png" alt="Reacao final congelada" style="width:1080px;height:{cam_h}px;object-fit:cover;display:block;">
    </div>
    <div id="end-game-wrap">
      <img data-color-grading="{cg_attr}" id="end-game-img" src="assets/final_game_freeze.png" alt="Cena final congelada" style="width:1080px;height:{game_h}px;object-fit:cover;display:block;">
    </div>
    <div class="end-divider"></div>
    <div id="end-flash" class="clip" data-start="0" data-duration="0.24"></div>
    <div id="end-word-wrap" class="clip" data-start="0.08" data-duration="{max(0.3, ed_dur - 0.08):.2f}" data-layout-allow-safe-zone>
      <div id="end-word" data-var-text="end-card-word">{ed_word}</div>
    </div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo('#end-flash', {{ opacity: 0.96 }}, {{ opacity: 0, duration: 0.22, ease: 'power3.out' }}, 0);
    tl.fromTo('#end-game-img', {{ scale: 1.06 }}, {{ scale: 1.0, duration: 0.18, ease: 'power4.out' }}, 0);
    tl.fromTo('#end-word', {{ opacity: 0, scale: 1.32 }}, {{ opacity: 1, scale: 1.0, duration: 0.16, ease: 'power4.out' }}, 0.08);
    window.__timelines = window.__timelines || {{}};
    window.__timelines['abrupt-ending'] = tl;
  </script>
</template>
""",
            encoding="utf-8",
        )
        montadas.append(
            f'<div id="abrupt-ending" data-composition-id="abrupt-ending" data-composition-src="compositions/abrupt-ending.html" '
            f'data-start="{ed_start:.2f}" data-duration="{ed_dur:.2f}" data-track-index="1" data-track-kind="graphics" '
            f'data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:20;"></div>'
        )

    return montadas


def construir_projeto_hibrido(spec: dict, proj_dir: Path, limpar_tmp: bool = True) -> dict:
    ffmpeg = localizar_binario("ffmpeg")
    proj_dir = proj_dir.resolve()
    assets_dir = proj_dir / "assets"
    fonts_out = assets_dir / "fonts"
    sfx_out = assets_dir / "sfx"
    tmp_dir = proj_dir / "_tmp"
    fonts_out.mkdir(parents=True, exist_ok=True)
    sfx_out.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(FONTS_DIR / "Montserrat-ExtraBold.ttf", fonts_out / "Montserrat-ExtraBold.ttf")
    shutil.copy2(FONTS_DIR / "Anton-Regular.ttf", fonts_out / "Anton-Regular.ttf")

    # 1. Resolver video fonte e transcricao
    src_raw = spec["source"]
    src_video = Path(src_raw)
    if not src_video.exists():
        dl_s = hms_para_segundos(spec["source_start"]) if "source_start" in spec else None
        dl_e = hms_para_segundos(spec["source_end"]) if "source_end" in spec else None
        src_video = tmp_dir / "source_arc.mp4"
        baixar_ou_recortar_trecho(src_raw, dl_s, dl_e, src_video)

    _, W, H = medir_midia(src_video)
    cam_h = int(spec.get("cam_height", 600))
    game_h = CANVAS_H - cam_h

    # Resolver expressoes de crop
    crops_cfg = dict(spec.get("crops", {}))
    small_cam = crops_cfg.get("small_cam", "auto")
    if small_cam == "auto":
        _, _, rosto = detectar_facecam(src_video)
        if rosto is not None:
            cw, ch, cx, cy = calcular_crop_facecam(W, H, rosto, cam_h)
            small_cam = f"crop={cw}:{ch}:{cx}:{cy},scale=1080:{cam_h},setsar=1"
        else:
            small_cam = f"scale=1080:{cam_h}:force_original_aspect_ratio=increase,crop=1080:{cam_h},setsar=1"
    crops_cfg["small_cam"] = small_cam

    gw_def = _par(min(W, H * CANVAS_W / game_h))
    gh_def = _par(min(H, W * game_h / CANVAS_W))
    gx_def = _par((W - gw_def) / 2.0)
    gy_def = _par((H - gh_def) / 2.0)
    crops_cfg.setdefault("game_center", f"crop={gw_def}:{gh_def}:{gx_def}:{gy_def},scale=1080:{game_h},setsar=1")
    crops_cfg.setdefault("big_cam", small_cam)

    def _resolver_crop(chave_ou_expr: str, fallback_key: str) -> str:
        if not chave_ou_expr:
            return crops_cfg[fallback_key]
        return crops_cfg.get(chave_ou_expr, chave_ou_expr)

    def _cortar_split(s0: float, s1: float, out_p: Path, cam_f: str, game_f: str) -> None:
        dur = max(0.2, s1 - s0)
        filt = f"[0:v]{cam_f}[cam];[0:v]{game_f}[game];[cam][game]vstack=inputs=2,format=yuv420p[v]"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-v",
                "error",
                "-ss",
                f"{s0:.3f}",
                "-i",
                str(src_video),
                "-t",
                f"{dur:.3f}",
                "-filter_complex",
                filt,
                "-map",
                "[v]",
                "-map",
                "0:a:0?",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "16",
                "-r",
                "30",
                "-g",
                "15",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                str(out_p),
            ],
            check=True,
        )

    # 2. Montar todos os segmentos da historia
    meta_clips: list[dict] = []
    video_tags: list[str] = []
    t_cursor = 0.0

    for seg in spec["segments"]:
        cid = seg["id"]
        s0 = hms_para_segundos(seg["src_start"])
        s1 = hms_para_segundos(seg["src_end"])
        mode = seg.get("mode", "split")
        cam_f = _resolver_crop(seg.get("cam_crop", "small_cam"), "small_cam")
        game_f = _resolver_crop(seg.get("game_crop", "game_center"), "game_center")
        raw_out = tmp_dir / f"{cid}_raw.mp4"

        if mode == "split":
            _cortar_split(s0, s1, raw_out, cam_f, game_f)
        elif mode == "bigcam_punch":
            pa = hms_para_segundos(seg["punch_start"])
            pb = hms_para_segundos(seg["punch_end"])
            big_cam_f = _resolver_crop(seg.get("punch_cam_crop", "big_cam"), "big_cam")
            punch_game_f = _resolver_crop(seg.get("punch_game_crop", game_f), "game_center")
            p1, p2, p3 = tmp_dir / f"{cid}_p1.mp4", tmp_dir / f"{cid}_p2.mp4", tmp_dir / f"{cid}_p3.mp4"
            _cortar_split(s0, pa, p1, cam_f, game_f)
            _cortar_split(pa, pb, p2, big_cam_f, punch_game_f)
            _cortar_split(pb, s1, p3, cam_f, game_f)
            lst = tmp_dir / f"{cid}_concat.txt"
            lst.write_text(f"file '{p1.as_posix()}'\nfile '{p2.as_posix()}'\nfile '{p3.as_posix()}'\n", encoding="utf-8")
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(lst),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "16",
                    "-r",
                    "30",
                    "-g",
                    "15",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-ar",
                    "48000",
                    str(raw_out),
                ],
                check=True,
            )
        elif mode == "dissolve_special":
            dur_seg = max(0.5, s1 - s0)
            bg_parts = seg.get("bg_parts") or [
                {
                    "src_start": s0,
                    "duration": dur_seg,
                    "vf": f"crop={_par(H * 1080 / 1920)}:{H}:{_par((W - H * 1080 / 1920) / 2)}:0,scale=1080:1920,setsar=1,format=yuv420p",
                }
            ]
            bg_files = []
            for bi, bp in enumerate(bg_parts):
                bf = tmp_dir / f"{cid}_bg_{bi}.mp4"
                subprocess.run(
                    [
                        ffmpeg,
                        "-y",
                        "-v",
                        "error",
                        "-ss",
                        f"{hms_para_segundos(bp['src_start']):.3f}",
                        "-i",
                        str(src_video),
                        "-t",
                        f"{float(bp['duration']):.3f}",
                        "-vf",
                        bp["vf"],
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "16",
                        "-r",
                        "30",
                        "-g",
                        "15",
                        str(bf),
                    ],
                    check=True,
                )
                bg_files.append(bf)
            lst = tmp_dir / f"{cid}_diss_list.txt"
            lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in bg_files), encoding="utf-8")
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(lst),
                    "-ss",
                    f"{s0:.3f}",
                    "-t",
                    f"{dur_seg:.3f}",
                    "-i",
                    str(src_video),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0?",
                    "-t",
                    f"{dur_seg:.3f}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "16",
                    "-r",
                    "30",
                    "-g",
                    "15",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-ar",
                    "48000",
                    str(raw_out),
                ],
                check=True,
            )
            fc = seg.get("face_overlay", {})
            fs0 = hms_para_segundos(fc.get("src_start", s0))
            fdur = float(fc.get("src_duration", min(2.0, dur_seg)))
            slow_pts = max(1.0, dur_seg / max(0.2, fdur))
            face_vf = fc.get(
                "vf",
                f"{_resolver_crop('big_cam', 'small_cam').replace(f'scale=1080:{cam_h}', 'scale=1080:716')},"
                f"pad=1080:1920:0:260:color=black,setpts={slow_pts:.2f}*PTS,setsar=1,format=yuv420p",
            )
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-v",
                    "error",
                    "-ss",
                    f"{fs0:.3f}",
                    "-i",
                    str(src_video),
                    "-t",
                    f"{fdur:.3f}",
                    "-vf",
                    face_vf,
                    "-an",
                    "-t",
                    f"{dur_seg:.2f}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "16",
                    "-r",
                    "30",
                    "-g",
                    "15",
                    str(assets_dir / "dissolve_face.mp4"),
                ],
                check=True,
            )
        else:
            raise ValueError(f"Modo de segmento desconhecido: {mode}")

        norm_out = assets_dir / f"{cid}.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-v",
                "error",
                "-i",
                str(raw_out),
                "-af",
                "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                str(norm_out),
            ],
            check=True,
        )
        real_dur, _, _ = medir_midia(norm_out)
        tl_start = round(t_cursor, 2)
        tl_dur = round(real_dur, 2)
        is_dissolve = mode == "dissolve_special"
        cg_html = f' data-color-grading="{COLOR_GRADE_DISSOLVE.replace(chr(34), "&quot;")}"' if is_dissolve else ""
        z_idx = 6 if is_dissolve else 1
        video_tags.append(
            f'<video{cg_html} id="{cid}" class="clip" src="assets/{cid}.mp4" '
            f'data-start="{tl_start:.2f}" data-duration="{tl_dur:.2f}" data-track-index="1" '
            f'data-has-audio="true" playsinline '
            f'style="position:absolute;inset:0;width:1080px;height:1920px;object-fit:cover;z-index:{z_idx};"></video>'
        )
        meta_clips.append(
            {
                "id": cid,
                "file": f"assets/{cid}.mp4",
                "srcStart": s0,
                "srcEnd": s1,
                "tlStart": tl_start,
                "duration": tl_dur,
                "mode": mode,
                "suppressCaptions": bool(seg.get("suppress_captions", is_dissolve)),
            }
        )
        t_cursor = round(tl_start + tl_dur, 2)

    # 3. Extrair imagens auxiliares (HUD Callout e Final Freeze)
    overlays_cfg = spec.get("overlays", {})
    hud_cfg = overlays_cfg.get("hud_callout")
    if hud_cfg:
        if hud_cfg.get("image_path") and Path(hud_cfg["image_path"]).exists():
            shutil.copy2(hud_cfg["image_path"], assets_dir / "hud_callout.png")
        else:
            at_s = hms_para_segundos(hud_cfg.get("crop_at_sec", meta_clips[0]["srcStart"]))
            vf_crop = hud_cfg.get("crop_filter", "crop=250:125:1670:60,scale=420:-1")
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-v",
                    "error",
                    "-ss",
                    f"{at_s:.3f}",
                    "-i",
                    str(src_video),
                    "-frames:v",
                    "1",
                    "-vf",
                    vf_crop,
                    str(assets_dir / "hud_callout.png"),
                ],
                check=True,
            )

    ending_cfg = overlays_cfg.get("abrupt_ending")
    video_end_t = t_cursor
    total_dur = t_cursor
    if ending_cfg:
        ending_cfg = dict(ending_cfg)
        ending_cfg.setdefault("start", video_end_t)
        ed_dur = float(ending_cfg.get("duration", 1.35))
        freeze_s = hms_para_segundos(ending_cfg.get("freeze_at_sec", max(0.0, meta_clips[-1]["srcEnd"] - 0.15)))
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-v",
                "error",
                "-ss",
                f"{freeze_s:.3f}",
                "-i",
                str(src_video),
                "-frames:v",
                "1",
                "-vf",
                crops_cfg["small_cam"],
                str(assets_dir / "final_face_freeze.png"),
            ],
            check=True,
        )
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-v",
                "error",
                "-ss",
                f"{freeze_s:.3f}",
                "-i",
                str(src_video),
                "-frames:v",
                "1",
                "-vf",
                crops_cfg["game_center"],
                str(assets_dir / "final_game_freeze.png"),
            ],
            check=True,
        )
        total_dur = round(float(ending_cfg["start"]) + ed_dur, 2)

    # 4. Banner do Gancho
    hook_cfg = dict(spec.get("hook_banner", {"text": "OLHA O QUE *ACONTECEU!*", "duration": 3.88}))
    gerar_png_banner_enrolando(hook_cfg["text"], assets_dir / "banner_gancho.png", escurecer_fundo=True)

    # 5. Remapear Legendas da Transcricao (sem bug de start > end)
    tr_path = spec.get("transcript")
    if tr_path and Path(tr_path).exists():
        tr_data = json.loads(Path(tr_path).read_text(encoding="utf-8"))
    else:
        tr_data = transcrever_completo(src_video, idioma=spec.get("idioma", "pt"), modelo=spec.get("whisper_modelo", "large-v3-turbo"))
    src_words = tr_data.get("words") or [w for s in tr_data.get("segments", []) for w in s.get("words", [])]

    rewind_cfg = overlays_cfg.get("rewind_badge")
    dissolve_cfg = overlays_cfg.get("joke_dissolve")
    if dissolve_cfg and "start" not in dissolve_cfg:
        diss_seg = next((c for c in meta_clips if c["mode"] == "dissolve_special"), None)
        if diss_seg:
            dissolve_cfg = dict(dissolve_cfg, start=diss_seg["tlStart"], duration=diss_seg["duration"])

    no_cap_windows: list[tuple[float, float]] = [(0.0, float(hook_cfg.get("duration", 3.88)))]
    if rewind_cfg:
        rw_s = float(rewind_cfg["start"])
        no_cap_windows.append((rw_s, rw_s + min(1.45, float(rewind_cfg.get("duration", 1.85)))))
    if dissolve_cfg:
        ds_s = float(dissolve_cfg["start"])
        no_cap_windows.append((ds_s, ds_s + float(dissolve_cfg.get("duration", 5.0))))

    remapped_words = []
    for seg_m in meta_clips:
        if seg_m["suppressCaptions"]:
            continue
        s0, s1, tl0 = seg_m["srcStart"], seg_m["srcEnd"], seg_m["tlStart"]
        for w in src_words:
            ws, we = float(w["start"]), float(w["end"])
            if ws >= s0 + 0.04 and we <= s1 - 0.04:
                tl_s = round(tl0 + (ws - s0), 3)
                tl_e = round(max(tl_s + 0.08, tl0 + (we - s0)), 3)
                if any(tl_s < win_e and tl_e > win_s for win_s, win_e in no_cap_windows):
                    continue
                txt = (w.get("word") or w.get("text") or "").strip()
                if txt:
                    remapped_words.append({"text": txt.upper(), "start": tl_s, "end": tl_e})

    captions_dur = video_end_t
    caption_groups = agrupar_legendas(remapped_words, captions_dur, max_end=captions_dur - 0.10)
    (proj_dir / "timeline_meta.json").write_text(
        json.dumps({"clips": meta_clips, "captions": caption_groups}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 6. Escrever Sub-composicoes
    comp_hosts = _escrever_subcomposicoes_hibrido(
        proj_dir / "compositions",
        cam_h=cam_h,
        game_h=game_h,
        hook_cfg=hook_cfg,
        rewind_cfg=rewind_cfg,
        promise_cfg=overlays_cfg.get("promise_goal"),
        hud_cfg=hud_cfg,
        dissolve_cfg=dissolve_cfg,
        ending_cfg=ending_cfg,
        captions_groups=caption_groups,
        captions_dur=captions_dur,
        captions_y=int(spec.get("captions_y", 1110)),
    )

    # 7. Preparar SFX e BGM (copiando do kit embutido ou caminho informado)
    audio_tags: list[str] = []
    # SFX automatico do papel na abertura
    shutil.copy2(SFX_DIR / "papel_enrolando.wav", sfx_out / "papel_enrolando.wav")
    hb_sfx_dur = min(float(hook_cfg.get("duration", 3.88)), total_dur)
    audio_tags.append(
        f'<audio id="sfx-paper-open" class="clip" src="assets/sfx/papel_enrolando.wav" '
        f'data-start="0.00" data-duration="{hb_sfx_dur:.2f}" data-track-index="5" data-volume="0.34"></audio>'
    )

    for idx, item in enumerate(spec.get("audio", [])):
        aid = item.get("id") or f"audio-{idx + 1}"
        src_name = item["src"]
        cand_local = Path(src_name)
        cand_kit = SFX_DIR / src_name
        origem = cand_local if cand_local.exists() else cand_kit
        if not origem.exists():
            raise FileNotFoundError(f"Arquivo de audio nao encontrado no caminho nem no kit da skill: {src_name}")
        dest_audio = sfx_out / origem.name
        if not dest_audio.exists():
            shutil.copy2(origem, dest_audio)
        dur_a, _, _ = medir_midia(dest_audio)
        st = float(item["start"])
        du = float(item.get("duration", min(dur_a, max(0.2, total_dur - st))))
        vol = float(item.get("volume", 0.35))
        trk = int(item.get("track", 4))
        fi = f' data-fade-in="{float(item["fade_in"]):.2f}"' if "fade_in" in item else ""
        fo = f' data-fade-out="{float(item["fade_out"]):.2f}"' if "fade_out" in item else ""
        audio_tags.append(
            f'<audio id="{aid}" class="clip" src="assets/sfx/{dest_audio.name}" '
            f'data-start="{st:.2f}" data-duration="{du:.2f}" data-track-index="{trk}" '
            f'data-volume="{vol:.2f}"{fi}{fo}></audio>'
        )

    # 8. Montar index.html raiz limpo e editavel no HyperFrames Studio
    vars_list = [
        {"id": "color-accent", "type": "color", "label": "Destaque", "default": "#FFE500"},
        {"id": "color-danger", "type": "color", "label": "Alerta / GTA", "default": "#E51A2E"},
    ]
    if overlays_cfg.get("promise_goal"):
        vars_list.append(
            {"id": "goal-label", "type": "string", "label": "Promessa (Objetivo)", "default": overlays_cfg["promise_goal"].get("label", "")}
        )
    if dissolve_cfg:
        vars_list.append(
            {"id": "dissolve-label", "type": "string", "label": "Texto do Dissolve", "default": dissolve_cfg.get("label", "")}
        )
    if ending_cfg:
        vars_list.append(
            {"id": "end-card-word", "type": "string", "label": "Card Final Abrupto", "default": ending_cfg.get("word", "")}
        )
    vars_attr = json.dumps(vars_list, ensure_ascii=False).replace('"', "&quot;")
    titulo_doc = spec.get("title", "Corte Híbrido Narrativo")

    nl = "\n    "
    root_html = f"""<!DOCTYPE html>
<html lang="pt-BR" data-composition-variables="{vars_attr}">
<head>
  <meta charset="utf-8">
  <title>{titulo_doc}</title>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: #000000; }}
    #root {{ position: relative; width: 1080px; height: 1920px; background: #000000; overflow: hidden; }}
    .split-divider {{
      position: absolute; top: {cam_h - 1}px; left: 0; width: 1080px; height: 3px;
      background: rgba(11, 11, 15, 0.90); box-shadow: 0 2px 10px rgba(0, 0, 0, 0.75);
      z-index: 4; pointer-events: none;
    }}
  </style>
</head>
<body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{total_dur:.2f}" data-width="1080" data-height="1920">
    {nl.join(video_tags)}
    <div class="split-divider"></div>
    {nl.join(comp_hosts)}
    {nl.join(audio_tags)}
  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    window.__timelines['main'] = gsap.timeline({{ paused: true }});
  </script>
</body>
</html>
"""
    index_path = proj_dir / "index.html"
    index_path.write_text(root_html, encoding="utf-8")

    if limpar_tmp:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {
        "projeto_hyperframes": str(proj_dir),
        "index_html": str(index_path),
        "duracao_total_s": total_dur,
        "segmentos": len(meta_clips),
        "grupos_legenda": len(caption_groups),
    }


def cmd_hybrid(args: argparse.Namespace) -> None:
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    res = construir_projeto_hibrido(spec, Path(args.saida_dir), limpar_tmp=not args.manter_tmp)
    print(json.dumps(res, ensure_ascii=False, indent=2))


# =====================================================================
# 8. Gerador Padronizado do Arquivo .txt de SEO Multirede
# =====================================================================
def gerar_txt_seo(
    destino_txt: Path,
    *,
    video_nome: str,
    yt_titulo: str,
    yt_descricao: str,
    yt_tags: list[str],
    ig_legenda: str,
    ig_alt_text: str,
    ig_hashtags: list[str],
    tt_legenda: str,
    tt_hashtags: list[str],
    creditos: list[dict],
) -> Path:
    def _fmt_tags(lst: list[str]) -> str:
        return " ".join(h if h.startswith("#") else f"#{h}" for h in lst[:5])

    cred_linhas = "\n".join(f"- {c['nome']}: {c['url']}" for c in creditos if c.get("url"))
    cred_inline = ", ".join(
        f"{c['nome']} ({c['url']})" if c.get("url") else c["nome"] for c in creditos if c.get("nome")
    )
    yt_t = yt_titulo[:60].strip()
    tags_csv = ", ".join(t.lstrip("#").strip() for t in yt_tags if t.strip())

    conteudo = f"""======================================================================
DESCRICOES OTIMIZADAS (SEO) — {video_nome}
======================================================================


----------------------------------------------------------------------
1) YOUTUBE SHORTS (youtube-seo + social-seo)
----------------------------------------------------------------------

[TITULO — {len(yt_t)} caracteres]
{yt_t}

[DESCRICAO PARA COPIAR]
{yt_descricao.strip()}

Créditos do vídeo original:
{cred_linhas}

{_fmt_tags(yt_tags[:5])}

[TAGS]
{tags_csv}


----------------------------------------------------------------------
2) INSTAGRAM REELS (instagram-seo — Framework MATCH)
----------------------------------------------------------------------

[LEGENDA PARA COPIAR]
{ig_legenda.strip()}

Créditos: {cred_inline}

{_fmt_tags(ig_hashtags)}

[ALT TEXT SUGERIDO]
{ig_alt_text.strip()}


----------------------------------------------------------------------
3) TIKTOK (tiktok-captions + social-seo — Triple Mention)
----------------------------------------------------------------------

[LEGENDA PARA COPIAR]
{tt_legenda.strip()}

Créditos: {cred_inline}

{_fmt_tags(tt_hashtags)}
"""
    destino_txt.parent.mkdir(parents=True, exist_ok=True)
    destino_txt.write_text(conteudo, encoding="utf-8")
    return destino_txt


def cmd_seo_txt(args: argparse.Namespace) -> None:
    cfg = json.loads(Path(args.json).read_text(encoding="utf-8"))
    out = gerar_txt_seo(
        Path(args.output),
        video_nome=cfg["video_nome"],
        yt_titulo=cfg["youtube"]["titulo"],
        yt_descricao=cfg["youtube"]["descricao"],
        yt_tags=cfg["youtube"]["tags"],
        ig_legenda=cfg["instagram"]["legenda"],
        ig_alt_text=cfg["instagram"]["alt_text"],
        ig_hashtags=cfg["instagram"]["hashtags"],
        tt_legenda=cfg["tiktok"]["legenda"],
        tt_hashtags=cfg["tiktok"]["hashtags"],
        creditos=cfg.get("creditos", []),
    )
    print(json.dumps({"seo_txt": str(out)}, ensure_ascii=False))


# =====================================================================
# 9. Self-Test (Valida Geracao 1 Batch e Geracao 2 Hybrid)
# =====================================================================
def cmd_self_test(args: argparse.Namespace) -> None:
    ffmpeg = localizar_binario("ffmpeg")
    base = Path(args.saida_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)

    # Video sintetico 16:9 (1920x1080, 14s) para testar ambos os modos
    src_16x9 = base / "synth_source_16x9.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=1920x1080:rate=30:duration=14",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=14",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-g",
            "15",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            str(src_16x9),
        ],
        check=True,
    )

    tr_fake = {
        "language": "pt",
        "duration": 14.0,
        "words": [
            {"word": "OLHA", "start": 0.4, "end": 0.8},
            {"word": "ESSE", "start": 0.8, "end": 1.2},
            {"word": "CORVETTE", "start": 1.2, "end": 1.8},
            {"word": "AGORA", "start": 4.2, "end": 4.6},
            {"word": "VAMOS", "start": 4.6, "end": 5.0},
            {"word": "TUNAR!", "start": 5.0, "end": 5.6},
            {"word": "FALTOU", "start": 10.4, "end": 10.9},
            {"word": "CINCO", "start": 10.9, "end": 11.3},
            {"word": "DÓLARES!", "start": 11.3, "end": 12.0},
            {"word": "RUIM", "start": 13.4, "end": 13.7},
            {"word": "HEIN.", "start": 13.7, "end": 13.95},
        ],
    }
    tr_path = base / "synth_transcript.json"
    tr_path.write_text(json.dumps(tr_fake, ensure_ascii=False), encoding="utf-8")

    # 1) Teste Batch Individual
    split_ind = base / "synth_split.mp4"
    gerar_split_vertical(src_16x9, split_ind, duracao_alvo=6.5, facecam_mode="64,72,380,212", cam_h=768)
    banner_tmp = base / "synth_banner.png"
    gerar_png_banner_enrolando("Quando o lugar não aceita *Pix*", banner_tmp)
    grupos_ind = agrupar_legendas(
        [{"text": w["word"], "start": w["start"], "end": w["end"]} for w in tr_fake["words"][:6]], 6.5
    )
    p_batch = base / "test_batch"
    gerar_projeto_hf_individual(p_batch, split_ind, banner_tmp, 6.5, grupos_ind, "Quando o lugar não aceita Pix")

    # 2) Teste Hybrid Narrativo completo (com todos os 7 sub-componentes)
    spec_hybrid = {
        "title": "Self-Test Híbrido",
        "source": str(src_16x9),
        "transcript": str(tr_path),
        "cam_height": 600,
        "crops": {
            "small_cam": "crop=382:212:68:82,scale=1080:600,setsar=1",
            "big_cam": "crop=770:428:136:156,scale=1080:600,setsar=1",
            "game_center": "crop=884:1080:518:0,scale=1080:1320,setsar=1",
        },
        "hook_banner": {"text": "ELE ROUBOU UM CORVETTE *E FICOU SEM GASOLINA!*", "duration": 3.20},
        "segments": [
            {"id": "seg00_cold_open", "src_start": 10.2, "src_end": 13.4, "mode": "split", "suppress_captions": True},
            {"id": "seg01_story", "src_start": 0.2, "src_end": 6.2, "mode": "bigcam_punch", "punch_start": 2.2, "punch_end": 3.6},
            {
                "id": "seg02_dissolve",
                "src_start": 6.2,
                "src_end": 9.2,
                "mode": "dissolve_special",
                "face_overlay": {"src_start": 6.4, "src_duration": 1.5},
            },
            {"id": "seg03_finale", "src_start": 10.2, "src_end": 13.9, "mode": "split"},
        ],
        "overlays": {
            "rewind_badge": {"start": 3.20, "duration": 1.50, "label": "VOLTANDO NO TEMPO"},
            "promise_goal": {"start": 5.00, "duration": 2.40, "kicker": "OBJETIVO:", "label": "TUNAR O CORVETTE!"},
            "hud_callout": {
                "start": 7.60,
                "duration": 1.50,
                "crop_at_sec": 7.0,
                "crop_filter": "crop=250:125:1600:60,scale=420:-1",
                "top_label": "GASOLINA: $48",
                "bottom_label": "FALTA $5 NO BOLSO!",
            },
            "joke_dissolve": {"label": "*FALTAVAM $5 NO BOLSO*"},
            "abrupt_ending": {"duration": 2.10, "freeze_at_sec": 13.6, "word": "sem gasosa"},
        },
        "audio": [
            {"id": "sfx-bass-open", "src": "impact_bass.mp3", "start": 0.0, "duration": 1.5, "volume": 0.36, "track": 4},
            {"id": "sfx-rewind", "src": "record_scratch.mp3", "start": 3.20, "duration": 0.65, "volume": 0.50, "track": 4},
            {"id": "sfx-wasted", "src": "wasted_boom.mp3", "start": 15.90, "duration": 1.35, "volume": 0.65, "track": 4},
            {"id": "bgm-chase", "src": "chase_loop.mp3", "start": 3.20, "duration": 12.0, "volume": 0.09, "track": 6, "fade_in": 0.4, "fade_out": 0.8},
        ],
    }
    p_hybrid = base / "test_hybrid"
    res_hyb = construir_projeto_hibrido(spec_hybrid, p_hybrid, limpar_tmp=True)

    print(json.dumps({"batch": str(p_batch), "hybrid": res_hyb}, ensure_ascii=False, indent=2))


# =====================================================================
# 10. Parser CLI Principal
# =====================================================================
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Motor unificado Cutter Pipeline (Geracao 1: Lote | Geracao 2: Hibrido Narrativo).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="Diagnostica Python, CUDA, FFmpeg, YuNet, Chrome e HyperFrames CLI.")

    p_set = sub.add_parser("setup", help="Cria .venv e instala dependencias de midia/transcricao automaticamente.")
    p_set.add_argument("--venv-dir", default=None, help="Diretorio do ambiente virtual (padrao: ./.venv)")

    p_md = sub.add_parser("parse-md", help="Interpreta um arquivo .md com intervalos/timestamps e ganchos.")
    p_md.add_argument("arquivo")

    p_ext = sub.add_parser("extract", help="Baixa/recorta video ou audio, transcreve com Whisper e gera overview.jpg.")
    p_ext.add_argument("--fonte", required=True, help="URL (YouTube/Twitch/Kick) ou arquivo de video local")
    p_ext.add_argument("--inicio", default=None, help="Timestamp inicial opcional (HH:MM:SS ou s)")
    p_ext.add_argument("--fim", default=None, help="Timestamp final opcional (HH:MM:SS ou s)")
    p_ext.add_argument("--apenas-audio", action="store_true", help="Baixa somente o audio (mais rapido para lives longas)")
    p_ext.add_argument("--idioma", default="pt")
    p_ext.add_argument("--whisper-modelo", default="large-v3-turbo")
    p_ext.add_argument("--grid-step", type=float, default=0.0, help="Segundos entre quadros no overview.jpg (0 = auto)")
    p_ext.add_argument("--saida-dir", required=True)

    p_ev = sub.add_parser("evidence", help="Gera prancha de frames (contact sheet) de um intervalo especifico.")
    p_ev.add_argument("--video", required=True)
    p_ev.add_argument("--inicio", default="0")
    p_ev.add_argument("--fim", default=None)
    p_ev.add_argument("--step", type=float, default=1.0, help="Passo em segundos entre quadros")
    p_ev.add_argument("--cols", type=int, default=4)
    p_ev.add_argument("--saida", required=True)

    p_cam = sub.add_parser("detect-cam", help="Detecta coordenadas da facecam via YuNet e sugere expressoes crop.")
    p_cam.add_argument("--video", required=True)

    p_bat = sub.add_parser("batch", help="Modo 1 (Producao em Lote): prepara cortes individuais com banner enrolando.")
    p_bat.add_argument("--md", default=None, help="Arquivo .md com momentos e timestamps")
    p_bat.add_argument("--cortes", default="all", help="Numeros ou slugs separados por virgula, ou 'all'")
    p_bat.add_argument("--fonte", default=None)
    p_bat.add_argument("--inicio", default=None)
    p_bat.add_argument("--fim", default=None)
    p_bat.add_argument("--gancho", default=None)
    p_bat.add_argument("--slug", default=None)
    p_bat.add_argument("--resumo", default=None)
    p_bat.add_argument("--facecam", default="auto", help="auto, none ou x,y,w,h")
    p_bat.add_argument("--idioma", default="pt")
    p_bat.add_argument("--whisper-modelo", default="large-v3-turbo")
    p_bat.add_argument("--legenda-y", type=int, default=1140)
    p_bat.add_argument("--limpar-tmp", action="store_true")
    p_bat.add_argument("--saida-dir", required=True)

    p_top = sub.add_parser("batch-top", help="Variante Lote TOP: compilado estilo ranking 1..N com cadeados.")
    p_top.add_argument("--top-json", required=True)
    p_top.add_argument("--idioma", default="pt")
    p_top.add_argument("--whisper-modelo", default="large-v3-turbo")
    p_top.add_argument("--limpar-tmp", action="store_true")
    p_top.add_argument("--saida-dir", required=True)

    p_hyb = sub.add_parser("hybrid", help="Modo 2 (Padrao Hibrido Narrativo): monta projeto multi-composicao completo.")
    p_hyb.add_argument("--spec", required=True, help="Caminho para o story_spec.json")
    p_hyb.add_argument("--manter-tmp", action="store_true")
    p_hyb.add_argument("--saida-dir", required=True, help="Diretorio do projeto HyperFrames (ex: edicao/hf_meu-corte)")

    p_seo = sub.add_parser("seo-txt", help="Gera o arquivo .txt padronizado com SEO para Shorts, Reels e TikTok.")
    p_seo.add_argument("--json", required=True)
    p_seo.add_argument("-o", "--output", required=True)

    p_st = sub.add_parser("self-test", help="Gera projetos de teste para os modos Batch e Hybrid.")
    p_st.add_argument("--saida-dir", required=True)

    return ap


def main() -> None:
    garantir_ambiente_python()
    args = build_parser().parse_args()
    dispatch = {
        "doctor": cmd_doctor,
        "setup": cmd_setup,
        "parse-md": lambda a: print(json.dumps(parse_repurpose_md(Path(a.arquivo)), ensure_ascii=False, indent=2)),
        "extract": cmd_extract,
        "evidence": cmd_evidence,
        "detect-cam": cmd_detect_cam,
        "batch": cmd_batch,
        "batch-top": cmd_batch_top,
        "hybrid": cmd_hybrid,
        "seo-txt": cmd_seo_txt,
        "self-test": cmd_self_test,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
