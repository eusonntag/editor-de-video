"""Funções compartilhadas pelos scripts do editor: caminhos, estado do vídeo, nomes,
informações de mídia e leitura/gravação do .env.

Estrutura de pastas do aluno:
  videos/Para Editar/            vídeos brutos (nunca alterados nem apagados)
  videos/Para Editar/referencias vídeos de referência do formato react
  videos/Editados/               vídeos prontos: <nome>_editado[_vertical|_react].mp4 (+ .srt)
  videos/.trabalho/<id>/         intermediários de cada vídeo; <id> = nome do bruto sem extensão
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VIDEOS = RAIZ / "videos"
PARA_EDITAR = VIDEOS / "Para Editar"
REFERENCIAS = PARA_EDITAR / "referencias"
EDITADOS = VIDEOS / "Editados"
TRABALHO = VIDEOS / ".trabalho"
FONTES = RAIZ / "assets" / "fontes"
CONFIG = RAIZ / "config"
TOOLS = RAIZ / "tools"
ENV = RAIZ / ".env"

# o motion roda offline: sem telemetria, sem checar atualização e sem pedir feedback (vale para os subprocessos)
for _var in ("HYPERFRAMES_NO_TELEMETRY", "DO_NOT_TRACK", "HYPERFRAMES_NO_UPDATE_CHECK", "HYPERFRAMES_NO_FEEDBACK"):
    os.environ.setdefault(_var, "1")

EXTENSOES_VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
FORMATOS = ("horizontal", "vertical", "react")
SUFIXO_FORMATO = {"horizontal": "", "vertical": "_vertical", "react": "_react"}

# ordem das etapas; o status do vídeo é a última etapa concluída
ETAPAS = ["transcricao", "corte", "layout", "motion", "legenda", "final"]
NOME_ETAPA = {
    "transcricao": "Transcrição", "corte": "Corte", "layout": "Formato e zoom",
    "motion": "Motion", "legenda": "Legenda", "final": "Finalização",
}


# ------------------------------------------------------------------ sistema ----

def windows() -> bool:
    return os.name == "nt"


def python_venv() -> Path:
    return RAIZ / ".venv" / ("Scripts/python.exe" if windows() else "bin/python")


def bin_hyperframes() -> list[str]:
    local = RAIZ / "node_modules" / ".bin" / ("hyperframes.cmd" if windows() else "hyperframes")
    if local.exists():
        return [str(local)]
    return ["npx", "--no-install", "hyperframes"]


def rodar(cmd: list[str], silencioso: bool = True, **kw) -> subprocess.CompletedProcess:
    """subprocess.run com check e saída do ffmpeg escondida (erros aparecem se falhar)."""
    if silencioso and "stdout" not in kw and "capture_output" not in kw:
        kw["stdout"] = subprocess.DEVNULL
        kw.setdefault("stderr", subprocess.PIPE)
    try:
        return subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        raise SystemExit(f"falhou: {Path(cmd[0]).name} {' '.join(cmd[1:4])}…\n{err[-1500:]}") from None


def rodar_script(script: str, *args: str, quieto: bool = False) -> None:
    """Roda um script Python do projeto com o mesmo interpretador (venv) em modo UTF-8.
    quieto=True esconde a saída (ffmpeg é verboso) e só mostra o final se der erro."""
    caminho = RAIZ / script
    cmd = [sys.executable, "-X", "utf8", str(caminho), *map(str, args)]
    if not quieto:
        r = subprocess.run(cmd)
        if r.returncode:
            raise SystemExit(r.returncode)
        return
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        saida = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        print("\n".join(saida[-30:]))
        raise SystemExit(r.returncode)


# -------------------------------------------------------------------- mídia ----

def info_video(video: Path) -> dict:
    """largura, altura, fps (float), fps_int, duracao, tem_audio."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", str(video)],
        capture_output=True, text=True, check=True).stdout
    dados = json.loads(out)
    v = next((s for s in dados["streams"] if s.get("codec_type") == "video"), None)
    if v is None:
        raise SystemExit(f"sem faixa de vídeo: {video}")
    fps_str = v.get("r_frame_rate", "30/1")
    fps = float(Fraction(fps_str)) or 30.0
    return {
        "largura": int(v["width"]), "altura": int(v["height"]),
        "fps": fps, "fps_int": max(1, round(fps)), "fps_str": fps_str,
        "duracao": float(dados["format"].get("duration", 0)),
        "tem_audio": any(s.get("codec_type") == "audio" for s in dados["streams"]),
    }


def orientacao(info: dict) -> str:
    return "vertical" if info["altura"] > info["largura"] else "horizontal"


def fmt_tempo(seg: float) -> str:
    seg = max(0, int(round(seg)))
    return f"{seg // 60}:{seg % 60:02d}"


def gerar_onda(video: Path, destino: Path, pps: int = 50) -> None:
    """Picos de áudio (0–100) em pps valores por segundo, para o painel desenhar a onda."""
    import numpy as np

    sr = 8000
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr),
                        "-f", "s16le", "-"], capture_output=True)
    if r.returncode or not r.stdout:
        return
    x = np.abs(np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32)) / 32768
    janela = sr // pps
    n = len(x) // janela
    picos = x[: n * janela].reshape(n, janela).max(axis=1)
    ref = float(np.percentile(picos, 99)) or 1.0
    vals = np.clip(picos / ref * 100, 0, 100).round().astype(int).tolist()
    gravar_json(destino, {"pps": pps, "picos": vals})


def gerar_proxy(bruto: Path, destino: Path) -> None:
    """Cópia leve (H.264, 540p) do bruto para o painel: navegadores não tocam HEVC de celular/webcam."""
    tmp = destino.with_suffix(".tmp.mp4")
    rodar(["ffmpeg", "-y", "-i", str(bruto), "-vf", "scale=-2:540", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "30", "-g", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
           str(tmp)])
    os.replace(tmp, destino)


def ffmpeg_fontsdir() -> str:
    """Caminho da pasta de fontes escapado para o filtro ass/subtitles do ffmpeg."""
    p = FONTES.resolve().as_posix()
    return p.replace(":", r"\:").replace("'", r"\'")


# ------------------------------------------------------------------- vídeos ----

def listar_brutos() -> list[Path]:
    """Brutos de Para Editar + vídeos narrados (fundo + narração em .trabalho/<id>/<id>.mp4)."""
    brutos = [p for p in PARA_EDITAR.iterdir()
              if p.is_file() and p.suffix.lower() in EXTENSOES_VIDEO] if PARA_EDITAR.exists() else []
    if TRABALHO.exists():
        brutos += [p / f"{p.name}.mp4" for p in TRABALHO.iterdir()
                   if p.is_dir() and (p / "narracao.json").exists() and (p / f"{p.name}.mp4").exists()]
    return sorted(brutos, key=lambda p: p.stat().st_mtime)


def narrado(vid: str) -> dict | None:
    """Dados da narração (tipo ia ou audio) se o vídeo não tem câmera."""
    return ler_json(TRABALHO / vid / "narracao.json")


def achar_bruto(vid: str) -> Path:
    """Aceita o id (nome sem extensão), o nome do arquivo ou um caminho."""
    p = Path(vid)
    if p.suffix.lower() in EXTENSOES_VIDEO and p.exists():
        return p.resolve()
    for b in listar_brutos():
        if b.stem == vid or b.name == vid:
            return b
    raise SystemExit(f"vídeo \"{vid}\" não encontrado em {PARA_EDITAR}")


def id_video(vid: str) -> str:
    return achar_bruto(vid).stem


def pasta(vid: str) -> Path:
    p = TRABALHO / id_video(vid)
    p.mkdir(parents=True, exist_ok=True)
    return p


def pasta_formato(vid: str, formato: str) -> Path:
    p = pasta(vid) / formato
    p.mkdir(parents=True, exist_ok=True)
    return p


# ------------------------------------------------------------------- estado ----

def _estado_path(vid: str) -> Path:
    return TRABALHO / vid / "estado.json"


def ler_estado(vid: str) -> dict:
    p = _estado_path(vid)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"id": vid, "etapas": {}, "escolhas": {}, "arquivos_finais": {}}


def salvar_estado(vid: str, estado: dict) -> None:
    p = _estado_path(vid)
    p.parent.mkdir(parents=True, exist_ok=True)
    estado["atualizado"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


POR_FORMATO = {"layout", "motion", "legenda", "final"}


def marcar_etapa(vid: str, etapa: str, formato: str | None = None, **dados) -> None:
    """Etapas por formato (layout, motion, legenda, final) ficam em etapas[etapa][formato]."""
    e = ler_estado(vid)
    registro = {"feito": time.strftime("%Y-%m-%d %H:%M:%S"), **dados}
    etapas = e.setdefault("etapas", {})
    if etapa in POR_FORMATO:
        etapas.setdefault(etapa, {})[formato or "horizontal"] = registro
    else:
        etapas[etapa] = registro
    e["etapa_atual"] = None
    salvar_estado(vid, e)


def etapa_feita(vid: str, etapa: str, formato: str | None = None) -> dict | None:
    etapas = ler_estado(vid).get("etapas", {})
    if etapa in POR_FORMATO:
        return (etapas.get(etapa) or {}).get(formato or "horizontal")
    return etapas.get(etapa)


def desmarcar_a_partir(vid: str, etapa: str, formato: str | None = None) -> None:
    """Refazer uma etapa invalida as seguintes (ex.: novo corte → layout, motion, legenda).
    Com formato, só as etapas daquele formato."""
    e = ler_estado(vid)
    etapas = e.get("etapas", {})
    for nome in ETAPAS[ETAPAS.index(etapa):]:
        if formato and nome in POR_FORMATO:
            (etapas.get(nome) or {}).pop(formato, None)
        elif not formato:
            etapas.pop(nome, None)
    salvar_estado(vid, e)


def arquivo_atual(vid: str, formato: str) -> Path:
    """Vídeo mais avançado da cadeia de um formato: final (com legenda) → animado → base → cortado."""
    p = TRABALHO / vid
    f = p / formato
    for etapa, arq in (("legenda", f / "final.mp4"), ("motion", f / "animado.mp4"), ("layout", f / "base.mp4")):
        if etapa_feita(vid, etapa, formato) and arq.exists():
            return arq
    return p / "cortado.mp4"


def progresso(vid: str, etapa: str, passo: int, total: int, texto: str) -> None:
    """Grava a etapa em andamento (o painel mostra ao vivo) e imprime ⏳ Passo X/Y."""
    e = ler_estado(vid)
    e["etapa_atual"] = {"etapa": etapa, "passo": passo, "total": total, "texto": texto,
                        "inicio": time.strftime("%Y-%m-%d %H:%M:%S")}
    salvar_estado(vid, e)
    print(f"⏳ Passo {passo}/{total}: {texto}.", flush=True)


def status_video(vid: str) -> tuple[str, str]:
    """(emoji, descrição) — ⚪ novo, 🟡 em andamento, 🟢 editado."""
    e = ler_estado(vid)
    finais = e.get("arquivos_finais") or {}
    if finais:
        return "🟢", "editado → " + ", ".join(Path(f).name for f in finais.values())
    feitas = [x for x in ETAPAS if (e.get("etapas") or {}).get(x)]
    if not feitas and not (TRABALHO / vid).exists():
        return "⚪", "novo"
    if not feitas:
        return "🟡", "em andamento (começando)"
    return "🟡", f"em andamento ({NOME_ETAPA[feitas[-1]]} concluída)"


# -------------------------------------------------------------------- nomes ----

INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def limpar_nome(nome: str) -> str:
    """Nome seguro no Windows e no Mac: sem <>:"/\\|?*, espaços viram hífen, acentos mantidos."""
    n = INVALIDOS.sub("", nome.strip())
    n = re.sub(r"\s+", "-", n)
    n = re.sub(r"-{2,}", "-", n).strip("-.")
    for suf in (".mp4", ".mov", "_editado_vertical", "_editado_react", "_editado"):
        if n.lower().endswith(suf):
            n = n[: -len(suf)]
    if n.upper() in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(r"(?i)(COM|LPT)\d", n):
        n += "-video"
    return n[:80] or "video"


def caminho_final(nome: str, formato: str, versao: int = 1) -> Path:
    base = f"{nome}_editado{SUFIXO_FORMATO[formato]}"
    if versao > 1:
        base += f"-{versao}"
    return EDITADOS / f"{base}.mp4"


def proxima_versao_livre(nome: str, formato: str) -> Path:
    v = 2
    while caminho_final(nome, formato, v).exists():
        v += 1
    return caminho_final(nome, formato, v)


# ---------------------------------------------------------------------- env ----

def ler_env(chave: str) -> str:
    if ENV.exists():
        for linha in ENV.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha.startswith(f"{chave}="):
                return linha.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get(chave, "")


def gravar_env(chave: str, valor: str) -> None:
    linhas = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    novas, achou = [], False
    for linha in linhas:
        if linha.strip().startswith(f"{chave}="):
            novas.append(f"{chave}={valor}")
            achou = True
        else:
            novas.append(linha)
    if not achou:
        novas.append(f"{chave}={valor}")
    ENV.write_text("\n".join(novas) + "\n", encoding="utf-8")


def mascarar(valor: str) -> str:
    if not valor:
        return "(vazio)"
    if len(valor) <= 10:
        return valor[:2] + "…"
    return f"{valor[:6]}…{valor[-4:]}"


# -------------------------------------------------------------------- marca ----

def ler_marca() -> dict:
    p = CONFIG / "marca.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def ler_json(p: Path, padrao=None):
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return padrao


def gravar_json(p: Path, dados) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")


def copiar(origem: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem, destino)
