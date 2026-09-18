"""Diagnóstico e instalação do editor (só biblioteca padrão: roda antes do .venv existir).

  diagnostico [--json]      checa tudo e diz como resolver o que faltar
  instalar [--sistema] [--sim] [--local]
      sem opções: pastas, .venv + requirements, npm ci, video-use no commit fixado, índice de ícones
      --sistema   também instala FFmpeg/Node/Python/Git que faltarem (winget no Windows, Homebrew no Mac)
                  sem --sim só MOSTRA o que seria instalado (o comando pede confirmação ao aluno antes)
      --local     instala também a transcrição local (faster-whisper, ~200 MB + modelo na 1ª vez)
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WIN = os.name == "nt"
MAC = sys.platform == "darwin"
VENV_PY = RAIZ / ".venv" / ("Scripts/python.exe" if WIN else "bin/python")

# clones fixados (reprodutível). O HyperFrames vem pelo npm (package-lock.json).
VIDEO_USE = {"url": "https://github.com/browser-use/video-use.git", "commit": "9575612f",
             "pasta": RAIZ / "tools" / "video-use"}

PASTAS = ["videos/Para Editar/referencias", "videos/Editados", "videos/.trabalho", "config"]


def _saida(cmd: list[str], timeout: int = 30) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return (r.stdout or "") + (r.stderr or "") if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _versao(texto: str | None) -> str:
    if not texto:
        return ""
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", texto)
    return m.group(1) if m else texto.strip()[:20]


def _ler_env(chave: str) -> str:
    env = RAIZ / ".env"
    if env.exists():
        for linha in env.read_text(encoding="utf-8").splitlines():
            if linha.strip().startswith(chave + "="):
                return linha.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _mascarar(v: str) -> str:
    return f"{v[:6]}…{v[-4:]}" if len(v) > 10 else ("…" if v else "")


def python_para_venv() -> list[str] | None:
    """Python 3.10–3.13 preferido (3.14 ainda não tem todas as bibliotecas de transcrição local)."""
    candidatos: list[list[str]] = []
    if WIN:
        candidatos += [["py", f"-3.{v}"] for v in (12, 11, 13, 10)] + [["py", "-3"], ["python"]]
    else:
        candidatos += [[f"python3.{v}"] for v in (12, 11, 13, 10)] + [["python3"]]
    for c in candidatos:
        v = _versao(_saida([*c, "--version"]))
        if v and tuple(map(int, v.split(".")[:2])) >= (3, 10):
            return c
    return None


# -------------------------------------------------------------- diagnóstico ----

def diagnostico() -> dict:
    itens: list[dict] = []

    def item(chave, nome, ok, detalhe, resolver="", obrigatorio=True):
        itens.append({"chave": chave, "nome": nome, "ok": bool(ok), "detalhe": detalhe,
                      "resolver": resolver, "obrigatorio": obrigatorio})

    sistema = "Windows" if WIN else ("Mac" if MAC else platform.system())
    item("sistema", "Sistema", True, f"{sistema} {platform.machine()}")

    py = python_para_venv()
    item("python", "Python 3.10+", py is not None,
         f"{' '.join(py)} {_versao(_saida([*py, '--version']))}" if py else "não encontrado",
         "winget install Python.Python.3.12" if WIN else "brew install python@3.12")

    ffmpeg = _saida(["ffmpeg", "-hide_banner", "-version"])
    tem_ass = bool(ffmpeg) and " ass " in (_saida(["ffmpeg", "-hide_banner", "-filters"]) or "")
    tem_x264 = bool(ffmpeg) and "libx264" in (_saida(["ffmpeg", "-hide_banner", "-encoders"]) or "")
    item("ffmpeg", "FFmpeg (com legendas e H.264)", ffmpeg and tem_ass and tem_x264,
         (_versao(ffmpeg) + ("" if tem_ass and tem_x264 else " (sem libass/libx264)")) if ffmpeg else "não encontrado",
         "winget install Gyan.FFmpeg" if WIN else "brew install ffmpeg-full")
    item("ffprobe", "FFprobe", _saida(["ffprobe", "-version"]) is not None, "junto com o FFmpeg",
         "vem com o FFmpeg")

    node = _saida(["node", "--version"])
    node_ok = bool(node) and int(_versao(node).split(".")[0]) >= 22  # o HyperFrames exige Node 22+
    item("node", "Node.js 22+", node_ok, (_versao(node) + ("" if node_ok else " (antigo, precisa do 22 ou mais novo)"))
         if node else "não encontrado",
         "winget install OpenJS.NodeJS.LTS" if WIN else "brew install node")
    item("git", "Git", _saida(["git", "--version"]) is not None, _versao(_saida(["git", "--version"])) or "não encontrado",
         "winget install Git.Git" if WIN else "xcode-select --install")

    venv_ok = VENV_PY.exists()
    libs = None
    if venv_ok:
        libs = _saida([str(VENV_PY), "-c", "import numpy, cv2, requests, PIL, librosa; print('ok')"], timeout=60)
    item("venv", "Bibliotecas Python do projeto", venv_ok and libs is not None,
         "instaladas" if libs else ("ambiente .venv sem bibliotecas" if venv_ok else "ambiente .venv não criado"),
         "editor.py instalar")

    hf = RAIZ / "node_modules" / "hyperframes" / "package.json"
    gsap = RAIZ / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    icones = RAIZ / "node_modules" / "@phosphor-icons" / "core" / "assets"
    item("npm", "HyperFrames, GSAP e ícones (npm)", hf.exists() and gsap.exists() and icones.exists(),
         "instalados" if hf.exists() else "node_modules ausente", "editor.py instalar")

    chrome = None
    if hf.exists():
        hfbin = RAIZ / "node_modules" / ".bin" / ("hyperframes.cmd" if WIN else "hyperframes")
        chrome = _saida([str(hfbin), "browser", "path"], timeout=60)
    item("chrome", "Navegador de render do motion", bool(chrome and chrome.strip()),
         "pronto" if chrome else "será baixado na primeira renderização (~150 MB)",
         "editor.py instalar", obrigatorio=False)

    vu = VIDEO_USE["pasta"]
    commit = (_saida(["git", "-C", str(vu), "rev-parse", "--short=8", "HEAD"]) or "").strip()
    item("video-use", "Ferramenta de corte (video-use)", (vu / "helpers" / "render.py").exists(),
         f"commit {commit}" if commit else "não baixada", "editor.py instalar")

    fontes = list((RAIZ / "assets" / "fontes").glob("*.ttf"))
    item("fontes", "Fontes das legendas e motions", len(fontes) >= 5, f"{len(fontes)} fontes",
         "baixe o projeto de novo (assets/fontes)")

    indice = RAIZ / "motion" / "icones" / "indice.json"
    item("icones", "Índice de ícones", indice.exists(), "pronto" if indice.exists() else "não gerado",
         "editor.py icones indexar", obrigatorio=False)

    motor = _ler_env("TRANSCRICAO_MOTOR") or "groq"
    chaves = {"groq": "GROQ_API_KEY", "scribe": "ELEVENLABS_API_KEY"}
    if motor == "whisper":
        fw = venv_ok and _saida([str(VENV_PY), "-c", "import faster_whisper"], timeout=60) is not None
        item("transcricao", "Transcrição", fw, "no computador (Whisper local)" + ("" if fw else ", biblioteca não instalada"),
             "editor.py instalar --local")
    else:
        valor = _ler_env(chaves[motor])
        nome = {"groq": "Groq", "scribe": "ElevenLabs"}[motor]
        item("transcricao", "Transcrição", bool(valor),
             f"{nome}, chave {_mascarar(valor)}" if valor else f"{nome} escolhido, chave não configurada",
             "/configurar-transcricao")

    marca = RAIZ / "config" / "marca.json"
    item("marca", "Identidade visual", marca.exists(), "configurada" if marca.exists() else "usando o estilo padrão",
         "/video-marca", obrigatorio=False)

    pastas_ok = all((RAIZ / p).exists() for p in PASTAS)
    item("pastas", "Pastas de vídeos", pastas_ok, "videos/Para Editar e videos/Editados" if pastas_ok else "não criadas",
         "editor.py instalar")

    obrigatorios_ok = all(i["ok"] for i in itens if i["obrigatorio"])
    # "instalado": programas e bibliotecas prontos (a transcrição é configurada depois, no passo 4)
    instalado = all(i["ok"] for i in itens if i["obrigatorio"] and i["chave"] != "transcricao")
    return {"sistema": sistema, "pronto": obrigatorios_ok, "instalado": instalado, "itens": itens,
            "motor_transcricao": motor}


def imprimir_diagnostico(d: dict) -> None:
    for i in d["itens"]:
        marca = "✓" if i["ok"] else ("✗" if i["obrigatorio"] else "○")
        linha = f"{marca} {i['nome']}: {i['detalhe']}"
        if not i["ok"] and i["resolver"]:
            linha += f"  → {i['resolver']}"
        print(linha)
    print("PRONTO" if d["pronto"] else ("INSTALADO (falta configurar a transcrição)" if d["instalado"] else "FALTA ALGO"))


# ---------------------------------------------------------------- instalar ----

def _passo(n: int, total: int, texto: str) -> None:
    print(f"⏳ Passo {n}/{total}: {texto}.", flush=True)


def _rodar(cmd: list[str], **kw) -> bool:
    r = subprocess.run(cmd, **kw)
    return r.returncode == 0


def instalar_sistema(d: dict, executar: bool) -> list[str]:
    """Comandos para instalar o que falta no sistema. Só executa com executar=True."""
    faltando = {i["chave"] for i in d["itens"] if not i["ok"]}
    cmds: list[list[str]] = []
    if WIN:
        base = ["winget", "install", "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements", "--id"]
        pacotes = {"python": "Python.Python.3.12", "ffmpeg": "Gyan.FFmpeg", "node": "OpenJS.NodeJS.LTS", "git": "Git.Git"}
        for k, pid in pacotes.items():
            if k in faltando:
                cmds.append([*base, pid])
                if k == "node":  # Node antigo já instalado: "install" não troca de versão
                    cmds.append(["winget", "upgrade", "-e", "--silent", "--accept-package-agreements",
                                 "--accept-source-agreements", "--id", pid])
    elif MAC:
        if not shutil.which("brew"):
            cmds.append(["/bin/bash", "-c",
                         "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"])
        # "ffmpeg" do Homebrew vem sem libass (legendas); o completo é o "ffmpeg-full"
        pacotes = {"python": "python@3.12", "ffmpeg": "ffmpeg-full", "node": "node", "git": "git"}
        for k, pk in pacotes.items():
            if k in faltando:
                cmds.append(["brew", "install", pk])
    textos = [" ".join(c) for c in cmds]
    if executar:
        for c in cmds:
            print("→ " + " ".join(c[:4]) + " …", flush=True)
            if not _rodar(c):
                print(f"✗ falhou: {' '.join(c)}")
    return textos


def instalar(sistema: bool = False, executar_sistema: bool = False, local: bool = False) -> int:
    d = diagnostico()
    if sistema:
        cmds = instalar_sistema(d, executar_sistema)
        if cmds and not executar_sistema:
            print("SERIA INSTALADO NO SISTEMA:")
            for c in cmds:
                print("  " + c)
            return 0
        if cmds:
            print("Programas do sistema instalados. Feche e abra o terminal (ou o Claude Code) se algum não for encontrado.")
            d = diagnostico()

    faltam_base = [i["nome"] for i in d["itens"] if not i["ok"] and i["chave"] in {"python", "node", "git", "ffmpeg"}]
    if faltam_base:
        print("✗ Falta instalar no computador: " + ", ".join(faltam_base))
        print("  Rode: editor.py instalar --sistema")
        return 1

    total = 6
    _passo(1, total, "criar as pastas de vídeos")
    for p in PASTAS:
        (RAIZ / p).mkdir(parents=True, exist_ok=True)
    for p in ("videos/Para Editar", "videos/Para Editar/referencias", "videos/Editados"):
        (RAIZ / p / ".gitkeep").touch()

    _passo(2, total, "criar o ambiente Python do projeto")
    if not VENV_PY.exists():
        py = python_para_venv()
        if not _rodar([*py, "-m", "venv", str(RAIZ / ".venv")]):
            print("✗ não consegui criar o ambiente .venv")
            return 1
    _passo(3, total, "instalar as bibliotecas Python (1 a 3 minutos na primeira vez)")
    _rodar([str(VENV_PY), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    reqs = [str(RAIZ / "requirements.txt")]
    if local or _ler_env("TRANSCRICAO_MOTOR") == "whisper":
        reqs.append(str(RAIZ / "requirements-local.txt"))
    for r in reqs:
        if not _rodar([str(VENV_PY), "-m", "pip", "install", "-q", "-r", r]):
            print(f"✗ falhou a instalação de {Path(r).name}")
            return 1

    _passo(4, total, "instalar HyperFrames, GSAP e ícones")
    npm = "npm.cmd" if WIN else "npm"
    lock = RAIZ / "package-lock.json"
    if not _rodar([npm, "ci" if lock.exists() else "install", "--no-audit", "--no-fund", "--loglevel=error"], cwd=RAIZ):
        print("✗ falhou o npm")
        return 1

    _passo(5, total, "baixar a ferramenta de corte (video-use)")
    vu = VIDEO_USE["pasta"]
    if not (vu / ".git").exists():
        vu.parent.mkdir(exist_ok=True)
        if not _rodar(["git", "clone", "--quiet", VIDEO_USE["url"], str(vu)]):
            print("✗ não consegui baixar o video-use")
            return 1
    _rodar(["git", "-C", str(vu), "-c", "advice.detachedHead=false", "checkout", "--quiet", VIDEO_USE["commit"]])

    _passo(6, total, "preparar o índice de ícones e o navegador de render")
    _rodar([str(VENV_PY), "-X", "utf8", str(RAIZ / "scripts" / "icones.py"), "indexar"])
    hfbin = RAIZ / "node_modules" / ".bin" / ("hyperframes.cmd" if WIN else "hyperframes")
    _rodar([str(hfbin), "browser", "ensure"], stdout=subprocess.DEVNULL)

    d = diagnostico()
    imprimir_diagnostico(d)
    return 0 if d["instalado"] else 2


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "diagnostico":
        d = diagnostico()
        if "--json" in argv:
            print(json.dumps(d, ensure_ascii=False, indent=1))
        else:
            imprimir_diagnostico(d)
        return 0
    if argv[0] == "instalar":
        return instalar("--sistema" in argv, "--sim" in argv, "--local" in argv)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
