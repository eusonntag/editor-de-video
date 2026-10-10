"""Fundo musical: gerar com a ElevenLabs (Eleven Music) ou usar uma música do aluno, e mixar por baixo da voz.

A música é a última camada: entra no `finalizar` (e na prévia), sem refazer motion nem legenda.
Configuração do vídeo em videos/.trabalho/<id>/musica/musica.json:
  {"ativo": true, "trilha": "musica/trilha-1.mp3", "volume": "baixo|medio|alto", "abaixar_na_fala": true,
   "prompt": "...", "origem": "ia|arquivo"}

  amostras <trab> --prompts "a" "b" "c" [--duracao 15]     trechos curtos para escolher o gênero
  gerar <trab> --prompt "..." [--duracao s] [--modelo X]    trilha do tamanho do vídeo (+ 3 s)
  usar <trab> --arquivo musica.mp3                          música do aluno
  config <trab> [--trilha arq] [--volume X] [--abaixar sim|nao] [--desligar]
  previa <trab> --formato F                                 vídeo atual do formato + música → musica/previa_<F>.mp4
  mixar <video> <saida> --trab <trab>                       usado pelo finalizar
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402
from narrar import API, ErroNarracao, _erro_api, chave  # noqa: E402

# quanto a música fica abaixo da voz (dB de loudness); sem voz, usa -16 LUFS como referência
VOLUME = {"minimo": 24, "baixo": 18, "medio": 14, "alto": 10}
MODELO_PADRAO = "music_v1"


def pasta(trab: Path) -> Path:
    p = trab / "musica"
    p.mkdir(exist_ok=True)
    return p


def ler_config(trab: Path) -> dict:
    return C.ler_json(trab / "musica" / "musica.json", {}) or {}


def gravar_config(trab: Path, cfg: dict) -> None:
    C.gravar_json(pasta(trab) / "musica.json", cfg)


def compor(prompt: str, segundos: float, modelo: str) -> bytes:
    import requests

    corpo = {"prompt": prompt, "music_length_ms": int(min(600, max(3, segundos)) * 1000),
             "model_id": modelo, "force_instrumental": True}
    try:
        r = requests.post(f"{API}/v1/music?output_format=mp3_44100_128", json=corpo,
                          headers={"xi-api-key": chave()}, timeout=600)
    except requests.RequestException:
        raise ErroNarracao("✗ sem conexão com a ElevenLabs (internet caiu ou o serviço está fora do ar)")
    if r.status_code >= 400:
        msg = _erro_api(r)
        if r.status_code in (401, 403) and "permiss" in msg:
            msg = "a chave não tem permissão para música: libere \"Music\" na chave da ElevenLabs"
        elif r.status_code == 403:
            msg = "a ElevenLabs recusou: a música pela API pode exigir um plano pago (veja elevenlabs.io/pricing)"
        raise ErroNarracao("✗ " + msg)
    return r.content


def duracao(arq: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def loudness(video: Path) -> float | None:
    """Loudness integrado (LUFS) do áudio do vídeo."""
    import re

    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vn", "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    achados = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    if not achados:
        return None
    v = float(achados[-1])
    return v if v > -60 else None


def duracao_video(trab: Path) -> float:
    return C.info_video(trab / "cortado.mp4")["duracao"]


def cmd_amostras(a) -> None:
    trab = Path(a.trabalho)
    saida = pasta(trab) / "amostras"
    saida.mkdir(exist_ok=True)
    feitas = []
    for n, prompt in enumerate(a.prompts, 1):
        print(f"⏳ Passo {n}/{len(a.prompts)}: compor a amostra {n}.", flush=True)
        arq = saida / f"amostra-{n}.mp3"
        arq.write_bytes(compor(prompt, a.duracao, a.modelo))
        feitas.append({"n": n, "prompt": prompt, "arquivo": str(arq)})
    print(json.dumps({"amostras": feitas, "segundos": a.duracao * len(a.prompts)}, indent=1, ensure_ascii=False))


def cmd_gerar(a) -> None:
    trab = Path(a.trabalho)
    seg = a.duracao or duracao_video(trab) + 3
    p = pasta(trab)
    n = 1 + len(list(p.glob("trilha-*.mp3")))
    arq = p / f"trilha-{n}.mp3"
    arq.write_bytes(compor(a.prompt, seg, a.modelo))
    cfg = ler_config(trab)
    cfg.update({"ativo": True, "trilha": str(arq.relative_to(trab)).replace("\\", "/"), "origem": "ia",
                "prompt": a.prompt, "modelo": a.modelo})
    cfg.setdefault("volume", (C.ler_marca().get("musica") or {}).get("volume", "baixo"))
    cfg.setdefault("abaixar_na_fala", True)
    gravar_config(trab, cfg)
    print(json.dumps({"trilha": str(arq), "segundos": round(duracao(arq), 1), "pedido": round(seg, 1)},
                     ensure_ascii=False))


def cmd_usar(a) -> None:
    trab = Path(a.trabalho)
    orig = Path(a.arquivo)
    if not orig.exists():
        raise SystemExit(f"✗ música não encontrada: {orig}")
    destino = pasta(trab) / f"trilha-propria{orig.suffix.lower()}"
    shutil.copy2(orig, destino)
    cfg = ler_config(trab)
    cfg.update({"ativo": True, "trilha": str(destino.relative_to(trab)).replace("\\", "/"), "origem": "arquivo",
                "arquivo_original": str(orig)})
    cfg.setdefault("volume", (C.ler_marca().get("musica") or {}).get("volume", "baixo"))
    cfg.setdefault("abaixar_na_fala", True)
    gravar_config(trab, cfg)
    print(json.dumps({"trilha": str(destino), "segundos": round(duracao(destino), 1),
                      "video": round(duracao_video(trab), 1)}, ensure_ascii=False))


def cmd_config(a) -> None:
    trab = Path(a.trabalho)
    cfg = ler_config(trab)
    if a.desligar:
        cfg["ativo"] = False
    if a.trilha:
        cfg.update({"trilha": a.trilha, "ativo": True})
    if a.volume:
        cfg["volume"] = a.volume
    if a.abaixar:
        cfg["abaixar_na_fala"] = a.abaixar == "sim"
    gravar_config(trab, cfg)
    print(json.dumps(cfg, indent=1, ensure_ascii=False))


def mixar(video: Path, saida: Path, trab: Path) -> None:
    """Música em loop/cortada no tamanho do vídeo, com entrada e saída suaves e abaixando quando há fala."""
    cfg = ler_config(trab)
    trilha = trab / cfg["trilha"]
    if not trilha.exists():
        raise SystemExit(f"✗ trilha não encontrada: {trilha}")
    info = C.info_video(video)
    D = info["duracao"]
    voz = loudness(video) if info["tem_audio"] else None
    lufs = max(-40.0, min(-14.0, (voz if voz is not None else -16.0) - VOLUME.get(cfg.get("volume", "baixo"), 20)))
    fade = min(2.5, D / 4)
    musica = (f"[1:a]atrim=0:{D:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,"
              f"loudnorm=I={lufs}:TP=-3:LRA=11,aresample=48000,"
              f"afade=t=in:d=1,afade=t=out:st={max(0.0, D - fade):.3f}:d={fade:.3f}")
    if info["tem_audio"]:
        canais = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels",
                                 "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip()
        # mono → estéreo copiando o canal (o aformat padrão baixaria 3 dB na voz)
        voz = ("[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0" if canais == "1"
               else "[0:a]aformat=sample_rates=48000:channel_layouts=stereo")
        if cfg.get("abaixar_na_fala", True):
            filtro = (f"{musica}[m];{voz},asplit=2[v][sc];"
                      "[m][sc]sidechaincompress=threshold=0.04:ratio=4:attack=40:release=600[md];"
                      "[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:level=false[a]")
        else:
            filtro = f"{musica}[m];{voz}[v];[v][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:level=false[a]"
    else:
        filtro = f"{musica},alimiter=limit=0.95:level=false[a]"
    tmp = saida.with_suffix(".tmp.mp4")
    C.rodar(["ffmpeg", "-y", "-i", str(video), "-stream_loop", "-1", "-i", str(trilha), "-filter_complex", filtro,
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{D:.3f}",
             "-movflags", "+faststart", str(tmp)])
    tmp.replace(saida)


def cmd_previa(a) -> None:
    trab = Path(a.trabalho)
    vid = trab.name
    origem = C.arquivo_atual(vid, a.formato)
    destino = pasta(trab) / f"previa_{a.formato}.mp4"
    mixar(origem, destino, trab)
    print(f"prévia com música → {destino}")


def cmd_mixar(a) -> None:
    mixar(Path(a.video), Path(a.saida), Path(a.trab))


def main() -> None:
    ap = argparse.ArgumentParser(description="Fundo musical")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("amostras"); p.add_argument("trabalho"); p.add_argument("--prompts", nargs="+", required=True)
    p.add_argument("--duracao", type=float, default=15); p.add_argument("--modelo", default=MODELO_PADRAO)
    p = sub.add_parser("gerar"); p.add_argument("trabalho"); p.add_argument("--prompt", required=True)
    p.add_argument("--duracao", type=float); p.add_argument("--modelo", default=MODELO_PADRAO)
    p = sub.add_parser("usar"); p.add_argument("trabalho"); p.add_argument("--arquivo", required=True)
    p = sub.add_parser("config"); p.add_argument("trabalho"); p.add_argument("--trilha")
    p.add_argument("--volume", choices=list(VOLUME)); p.add_argument("--abaixar", choices=["sim", "nao"])
    p.add_argument("--desligar", action="store_true")
    p = sub.add_parser("previa"); p.add_argument("trabalho"); p.add_argument("--formato", required=True)
    p = sub.add_parser("mixar"); p.add_argument("video"); p.add_argument("saida"); p.add_argument("--trab", required=True)
    a = ap.parse_args()
    {"amostras": cmd_amostras, "gerar": cmd_gerar, "usar": cmd_usar, "config": cmd_config,
     "previa": cmd_previa, "mixar": cmd_mixar}[a.cmd](a)


if __name__ == "__main__":
    main()
