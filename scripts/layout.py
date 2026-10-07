"""Layout do vídeo cortado: formato (horizontal / vertical / react) + zooms da edição dinâmica,
numa passada só (a imagem é ampliada uma única vez, com interpolação subpixel e curvas suaves).

Entrada: <trabalho>/cortado.mp4, <trabalho>/dinamica.json (opcional), rosto (detectado aqui).
Saída:   <trabalho>/<formato>/base.mp4    (GOP denso: pronto para o HyperFrames)
         <trabalho>/<formato>/layout.json (áreas, rosto no quadro de saída, sugestão de legenda)

A duração não muda, então palavras.json continua valendo para cards e legendas.

Uso:
  python -X utf8 scripts/layout.py <trabalho> horizontal
  python -X utf8 scripts/layout.py <trabalho> vertical [--sem-zoom]
  python -X utf8 scripts/layout.py <trabalho> horizontal --previa   (zooms no rascunho: rascunho_sem_zoom.mp4 → rascunho.mp4)
  python -X utf8 scripts/layout.py <trabalho> react --referencia ref.mp4 [--orientacao vertical|horizontal]
      [--posicao cima|baixo|lado|pip] [--proporcao 50|40] [--inicio 0] [--fim 30]
      [--curta repetir|congelar|velocidade] [--audio mudo|baixo|auto] [--cor-linha "#c4ff5e"]
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import info_video, ler_marca, rodar  # noqa: E402
from desfoque import Desfoque, ler as ler_desfoque  # noqa: E402
from rosto import Trilha, rastrear  # noqa: E402


# ------------------------------------------------------------------ curvas ----

def _suave(x: float) -> float:
    """smootherstep: começa e termina parado (sem movimento linear)."""
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)


def _saida_cubica(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


class Zoom:
    def __init__(self, eventos: list[dict], fator_intensidade: float = 1.0):
        self.ev = []
        for e in eventos or []:
            if not e.get("ativo", True):
                continue
            e = dict(e)
            e["intensidade"] = 1 + (float(e["intensidade"]) - 1) * fator_intensidade
            self.ev.append(e)

    def maximo(self) -> float:
        z = 1.0
        for e in self.ev:
            z = max(z, e["intensidade"])
        punch = max([e["intensidade"] for e in self.ev if e["tipo"] == "punch"] or [1.0])
        aprox = max([e["intensidade"] for e in self.ev if e["tipo"] == "aproximacao"] or [1.0])
        return max(z, punch * aprox)

    def em(self, t: float) -> float:
        punch, enf, aprox = 1.0, 1.0, 1.0
        for e in self.ev:
            a, b, i = e["inicio"], e["fim"], e["intensidade"]
            if not (a <= t < b + 0.001):
                continue
            if e["tipo"] == "punch":
                punch = max(punch, i)                       # salto seco: acontece no corte
            elif e["tipo"] == "enfase":
                subida, descida = 0.28, 0.4
                env = _saida_cubica((t - a) / subida)
                if t > b - descida:
                    env = min(env, 1 - _suave((t - (b - descida)) / descida))
                enf = max(enf, 1 + (i - 1) * env)
            elif e["tipo"] == "aproximacao":
                aprox = max(aprox, 1 + (i - 1) * _suave((t - a) / max(0.1, b - a)))
        return max(punch, enf) * aprox


# ------------------------------------------------------------- enquadrador ----

class Enquadrador:
    """Calcula, quadro a quadro, a janela da origem que vira a imagem de saída."""

    def __init__(self, W: int, H: int, ow: int, oh: int, trilha: Trilha, zoom: Zoom,
                 seguir: bool | None = None, ancora_y: float | None = None, centro_x: float | None = None):
        self.W, self.H, self.ow, self.oh = W, H, ow, oh
        self.trilha, self.zoom = trilha, zoom
        aspecto = ow / oh
        if W / H > aspecto:
            self.bh, self.bw = float(H), H * aspecto
        else:
            self.bw, self.bh = float(W), W / aspecto
        med = trilha.dados["mediana"]
        # centro base fixo no rosto mediano; segue o rosto só se ele sair da janela fixa
        cx_base = centro_x if centro_x is not None else med["cx"]
        x0 = min(max(cx_base - self.bw / 2, 0), W - self.bw)
        fora = trilha.fracao_fora(x0, self.bw) if self.bw < W else 0.0
        self.seguir = (fora > 0.05) if seguir is None else seguir
        if centro_x is not None:
            self.seguir = False
        self.fora = fora
        self.cx_fixo = x0 + self.bw / 2
        if self.bh < H:
            # janela mais baixa que o quadro: rosto no terço de cima da saída (ancora_y)
            ay = 0.38 if ancora_y is None else ancora_y
            self.cy_fixo = min(max(med["cy"] + self.bh * (0.5 - ay), self.bh / 2), H - self.bh / 2)
        else:
            self.cy_fixo = H / 2

    def janela(self, t: float) -> tuple[float, float, float, float]:
        z = self.zoom.em(t)
        fx, fy = self.trilha.centro(t)
        if self.seguir:
            c0x = min(max(fx, self.bw / 2), self.W - self.bw / 2)
        else:
            c0x = self.cx_fixo
        c0y = self.cy_fixo
        w, h = self.bw / z, self.bh / z
        # zoom ancorado no rosto: o rosto fica no mesmo lugar da tela enquanto a imagem aproxima
        cx = fx + (c0x - fx) / z
        cy = fy + (c0y - fy) / z
        cx = min(max(cx, w / 2), self.W - w / 2)
        cy = min(max(cy, h / 2), self.H - h / 2)
        return cx - w / 2, cy - h / 2, w, h

    def matriz(self, t: float, escala_origem: float = 1.0) -> np.ndarray:
        x0, y0, w, h = self.janela(t)
        s = w / self.ow * escala_origem
        # mapeia saída → origem (usado com WARP_INVERSE_MAP), alinhando centros de pixel
        return np.array([[s, 0, x0 * escala_origem + s * 0.5 - 0.5],
                         [0, s, y0 * escala_origem + s * 0.5 - 0.5]], dtype=np.float64)

    def rosto_na_saida(self) -> dict:
        """Caixa do rosto no quadro de saída ao longo do vídeo (para posicionar cards e legenda)."""
        amostras = self.trilha.dados.get("amostras") or []
        if not amostras:
            m = self.trilha.dados["mediana"]
            amostras = [[0, m["cx"], m["cy"], m["w"], m["h"]]]
        caixas = []
        for t, cx, cy, fw, fh in amostras:
            x0, y0, w, h = self.janela(t)
            s = self.ow / w
            caixas.append(((cx - fw / 2 - x0) * s, (cy - fh / 2 - y0) * s, fw * s, fh * s))
        a = np.array(caixas)
        med = np.median(a, axis=0)
        # amostras a cada ~0,4 s: o motion calcula o espaço livre só no intervalo de cada card
        tempos = [s[0] for s in amostras]
        passo = max(1, int(round(0.4 / max(0.05, (tempos[-1] - tempos[0]) / max(1, len(tempos) - 1))))) if len(tempos) > 1 else 1
        return {
            "caixas": [[round(float(amostras[i][0]), 2), *[round(float(v)) for v in caixas[i]]]
                       for i in range(0, len(caixas), passo)],
            "mediana": [round(float(v)) for v in med],
            "uniao": [round(float(a[:, 0].min())), round(float(a[:, 1].min())),
                      round(float((a[:, 0] + a[:, 2]).max())), round(float((a[:, 1] + a[:, 3]).max()))],
            "topo_cabeca": round(float((a[:, 1] - 0.28 * a[:, 3]).min())),
            "queixo": round(float(np.percentile(a[:, 1] + a[:, 3] * 1.08, 90))),
            "obs": "caixa [x, y, largura, altura] do rosto (sobrancelha ao queixo) no quadro de saída",
        }


# ---------------------------------------------------------------- render ----

def renderizar_python(origem: Path, destino: Path, enq: Enquadrador, info: dict, com_audio: bool = True,
                      rapido: bool = False, desfoque: Desfoque | None = None) -> None:
    import cv2

    W, H = info["largura"], info["altura"]
    # resolução de trabalho: suficiente para o zoom máximo sem desperdiçar (vídeos 4K)
    fator = min(1.0, enq.oh * enq.zoom.maximo() / enq.bh)
    tw, th = int(round(W * fator / 2)) * 2, int(round(H * fator / 2)) * 2
    fator = tw / W
    dec_cmd = ["ffmpeg", "-v", "error", "-i", str(origem)]
    if fator < 0.999:
        dec_cmd += ["-vf", f"scale={tw}:{th}:flags=lanczos"]
    dec_cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    fps_int = info["fps_int"]
    enc_cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{enq.ow}x{enq.oh}", "-r", info["fps_str"], "-i", "-"]
    if com_audio and info["tem_audio"]:
        enc_cmd += ["-i", str(origem), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "128k" if rapido else "192k"]
    if rapido:
        # rascunho: só para conferir cortes e zooms (qualidade baixa, rápido)
        enc_cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-shortest", str(destino)]
    elif enq.bw / enq.ow < 0.95:
        # imagem ampliada (vertical/react a partir de horizontal): nitidez leve, como no pipeline antigo
        enc_cmd += ["-vf", "unsharp=5:5:0.4:5:5:0.0"]
    if not rapido:
        enc_cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-g", str(fps_int),
                    "-keyint_min", str(fps_int), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    "-shortest", str(destino)]
    dec = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE)
    enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)
    tam = tw * th * 3
    n = 0
    try:
        while True:
            buf = dec.stdout.read(tam)
            if len(buf) < tam:
                break
            quadro = np.frombuffer(buf, dtype=np.uint8).reshape(th, tw, 3)
            t = n / info["fps"]
            if desfoque:
                quadro = desfoque.aplicar(quadro, t)
            M = enq.matriz(t, fator)
            saida = cv2.warpAffine(quadro, M, (enq.ow, enq.oh), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
                                   borderMode=cv2.BORDER_REPLICATE)
            enc.stdin.write(saida.tobytes())
            n += 1
    finally:
        enc.stdin.close()
        dec.stdout.close()
        dec.wait()
        enc.wait()
    if enc.returncode:
        raise SystemExit("falhou a gravação do vídeo de layout")


def reencodar_gop(origem: Path, destino: Path, info: dict, ow: int, oh: int) -> None:
    vf = ["setsar=1"]
    if (ow, oh) != (info["largura"], info["altura"]):
        vf.insert(0, f"scale={ow}:{oh}:flags=lanczos")
    fps = str(info["fps_int"])
    rodar(["ffmpeg", "-y", "-i", str(origem), "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-g", fps, "-keyint_min", fps, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", str(destino)])


def tamanho_horizontal(info: dict) -> tuple[int, int]:
    W, H = info["largura"], info["altura"]
    esc = min(1.0, 1920 / max(W, H))
    return int(round(W * esc / 2)) * 2, int(round(H * esc / 2)) * 2


def legenda_vertical(rosto: dict, altura: int) -> dict:
    """Legenda abaixo da boca e acima da interface do Reels/TikTok (y ~1570)."""
    base = min(max(rosto["queixo"] + 170, 1330), 1560)
    return {"alinhamento": "baixo", "margem_v": altura - base}


# ------------------------------------------------------------------ react ----

def _atempo(f: float) -> str:
    partes = []
    while f > 2.0:
        partes.append("atempo=2.0")
        f /= 2.0
    while f < 0.5:
        partes.append("atempo=0.5")
        f /= 0.5
    partes.append(f"atempo={f:.5f}")
    return ",".join(partes)


def montar_react(trab: Path, a, info: dict, trilha: Trilha, zoom: Zoom, destino: Path,
                 desfoque: Desfoque | None = None) -> dict:
    ref = Path(a.referencia).resolve()
    if not ref.exists():
        raise SystemExit(f"vídeo de referência não encontrado: {ref}")
    iref = info_video(ref)
    marca = ler_marca()
    cor = (a.cor_linha or marca.get("cores", {}).get("destaque") or "#c4ff5e").lstrip("#")
    D = info["duracao"]
    vertical = a.orientacao == "vertical"
    OW, OH = (1080, 1920) if vertical else (1920, 1080)
    linha = 6

    if vertical:
        if a.posicao not in ("cima", "baixo"):
            a.posicao = "cima"
        ref_h = int(round(OH * (0.4 if a.proporcao == 40 else 0.5) / 2)) * 2
        voce_h = OH - ref_h
        ref_area = (0, 0 if a.posicao == "cima" else voce_h, OW, ref_h)
        voce_area = (0, ref_h if a.posicao == "cima" else 0, OW, voce_h)
        costura = ref_h if a.posicao == "cima" else voce_h
    elif a.posicao == "pip":
        ref_area = (0, 0, OW, OH)
        pw, ph = 576, 324
        voce_area = (OW - pw - 48, 48, pw, ph)
        costura = None
    else:
        a.posicao = "lado"
        ref_area = (0, 0, OW // 2, OH)
        voce_area = (OW // 2, 0, OW // 2, OH)
        costura = OW // 2

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # 1. você: recorte no rosto + zooms, no tamanho exato da sua área
        enq = Enquadrador(info["largura"], info["altura"], voce_area[2], voce_area[3], trilha, zoom,
                          ancora_y=0.42)
        voce = tmp / "voce.mp4"
        renderizar_python(trab / "cortado.mp4", voce, enq, info, desfoque=desfoque)

        # 2. trecho da referência, já no tamanho da área (preencher e cortar as sobras)
        ini = max(0.0, a.inicio or 0.0)
        fim = min(iref["duracao"], a.fim) if a.fim else iref["duracao"]
        ref_dur = max(0.1, fim - ini)
        rw, rh = ref_area[2], ref_area[3]
        trecho = tmp / "ref.mp4"
        cmd = ["ffmpeg", "-y", "-ss", f"{ini:.3f}", "-to", f"{fim:.3f}", "-i", str(ref),
               "-vf", f"scale={rw}:{rh}:force_original_aspect_ratio=increase,crop={rw}:{rh},fps={info['fps_str']},setsar=1",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p"]
        cmd += ["-c:a", "aac", "-ar", "48000", "-ac", "2"] if iref["tem_audio"] else ["-an"]
        rodar(cmd + [str(trecho)])

        # 3. empilhar + áudio
        audio = a.audio if iref["tem_audio"] else "mudo"
        entradas = ["-i", str(voce)]
        if ref_dur < D and a.curta == "repetir":
            entradas += ["-stream_loop", "-1"]
        entradas += ["-i", str(trecho)]
        fv = "[1:v]"
        cadeia_v, cadeia_a = [], []
        if ref_dur < D and a.curta == "congelar":
            cadeia_v.append(f"tpad=stop_mode=clone:stop_duration={D - ref_dur + 0.5:.3f}")
            cadeia_a.append(f"apad=pad_dur={D - ref_dur + 0.5:.3f}")
        elif a.curta == "velocidade" and abs(ref_dur - D) > 0.05:
            cadeia_v.append(f"setpts=PTS*{D / ref_dur:.6f}")
            cadeia_a.append(_atempo(ref_dur / D))
        cadeia_v += [f"trim=duration={D:.3f}", "setpts=PTS-STARTPTS"]
        filtros = [f"{fv}{','.join(cadeia_v)}[rv]"]

        if vertical:
            topo, baixo = ("[rv]", "[0:v]") if a.posicao == "cima" else ("[0:v]", "[rv]")
            filtros.append(f"{topo}{baixo}vstack=inputs=2,drawbox=x=0:y={costura - linha // 2}:w=iw:h={linha}:color=0x{cor}:t=fill[v]")
        elif a.posicao == "pip":
            x, y, pw, ph = voce_area
            filtros.append(f"[0:v]pad={pw + 12}:{ph + 12}:6:6:color=0x{cor}[pv]")
            filtros.append(f"[rv][pv]overlay={x - 6}:{y - 6}[v]")
        else:
            filtros.append(f"[rv][0:v]hstack=inputs=2,drawbox=x={costura - linha // 2}:y=0:w={linha}:h=ih:color=0x{cor}:t=fill[v]")

        tem_voz = info["tem_audio"]
        if audio == "mudo" or not tem_voz:
            mapa_a = ["-map", "0:a?"] if audio == "mudo" else ["-map", "1:a?"]
        else:
            ra = "[1:a]" + (",".join(cadeia_a) + "," if cadeia_a else "") + f"atrim=duration={D:.3f},asetpts=PTS-STARTPTS"
            if audio == "baixo":
                filtros.append(f"{ra},volume=0.15[ra]")
                filtros.append("[0:a][ra]amix=inputs=2:duration=first:normalize=0[a]")
            else:  # auto: abaixa sozinho quando você fala
                filtros.append(f"{ra},volume=0.8[ra]")
                filtros.append("[0:a]asplit=2[voz][sc]")
                filtros.append("[ra][sc]sidechaincompress=threshold=0.025:ratio=10:attack=20:release=350[duck]")
                filtros.append("[voz][duck]amix=inputs=2:duration=first:normalize=0[a]")
            mapa_a = ["-map", "[a]"]
        fps = str(info["fps_int"])
        rodar(["ffmpeg", "-y", *entradas, "-filter_complex", ";".join(filtros), "-map", "[v]", *mapa_a,
               "-t", f"{D:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-g", fps,
               "-keyint_min", fps, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", str(destino)])

    rosto = enq.rosto_na_saida()
    rosto["mediana"][0] += voce_area[0]
    rosto["mediana"][1] += voce_area[1]
    rosto["caixas"] = [[c[0], c[1] + voce_area[0], c[2] + voce_area[1], c[3], c[4]] for c in rosto["caixas"]]
    u = rosto["uniao"]
    rosto["uniao"] = [u[0] + voce_area[0], u[1] + voce_area[1], u[2] + voce_area[0], u[3] + voce_area[1]]
    rosto["topo_cabeca"] += voce_area[1]
    rosto["queixo"] += voce_area[1]
    if costura is not None and vertical:
        legenda = {"alinhamento": "centro", "centro_y": costura}
    elif costura is not None:
        legenda = {"alinhamento": "baixo", "margem_v": int(OH * 0.08)}
    else:
        legenda = {"alinhamento": "baixo", "margem_v": int(OH * 0.08)}
    return {
        "formato": "react", "largura": OW, "altura": OH, "orientacao": a.orientacao,
        "posicao": a.posicao, "proporcao": a.proporcao,
        "areas": {"voce": list(voce_area), "referencia": list(ref_area)}, "costura": costura,
        "referencia": {"arquivo": str(ref), "inicio": ini, "fim": fim, "duracao_trecho": round(ref_dur, 2),
                       "curta": a.curta if ref_dur < D else None, "audio": audio},
        "rosto": rosto, "legenda": legenda,
    }


# ------------------------------------------------------------------ main ----

def previa_zoom(trab: Path) -> None:
    """Rascunho com os zooms do jeito que vão ficar no horizontal (mesma linha do tempo do corte)."""
    origem = trab / "rascunho_sem_zoom.mp4"
    if not origem.exists():
        raise SystemExit("falta o rascunho do corte: rode o corte em rascunho antes")
    din = trab / "dinamica.json"
    eventos = json.loads(din.read_text(encoding="utf-8")).get("eventos", []) if din.exists() else []
    zoom = Zoom(eventos)
    desfoque = Desfoque(ler_desfoque(trab))
    destino = trab / "rascunho.mp4"
    if not zoom.ev and not desfoque:
        import shutil

        shutil.copyfile(origem, destino)
        print(f"rascunho sem zooms → {destino}")
        return
    info = info_video(origem)
    trilha = Trilha(rastrear(origem, trab / "rosto_rascunho.json"))
    enq = Enquadrador(info["largura"], info["altura"], info["largura"], info["altura"], trilha, zoom)
    renderizar_python(origem, destino, enq, info, rapido=True, desfoque=desfoque)
    print(f"rascunho com {len(zoom.ev)} zooms e {len(desfoque)} desfoques → {destino}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trabalho", type=Path)
    ap.add_argument("formato", choices=["horizontal", "vertical", "react"])
    ap.add_argument("--sem-zoom", action="store_true", help="Ignora dinamica.json")
    ap.add_argument("--seguir", choices=["auto", "sim", "nao"], default="auto",
                    help="Recorte acompanha o rosto (auto: só se ele sair do recorte fixo)")
    ap.add_argument("--centro-x", type=float, help="Força o centro horizontal do recorte (px do vídeo cortado)")
    ap.add_argument("--referencia")
    ap.add_argument("--orientacao", choices=["vertical", "horizontal"], default="vertical")
    ap.add_argument("--posicao", choices=["cima", "baixo", "lado", "pip"], default="cima")
    ap.add_argument("--proporcao", type=int, choices=[50, 40], default=50)
    ap.add_argument("--inicio", type=float, default=0.0)
    ap.add_argument("--fim", type=float)
    ap.add_argument("--curta", choices=["repetir", "congelar", "velocidade"], default="repetir")
    ap.add_argument("--audio", choices=["mudo", "baixo", "auto"], default="auto")
    ap.add_argument("--cor-linha")
    ap.add_argument("--previa", action="store_true",
                    help="Aplica os zooms no rascunho do corte (rascunho_sem_zoom.mp4 → rascunho.mp4), para aprovar junto")
    a = ap.parse_args()

    trab = a.trabalho.resolve()
    if a.previa:
        previa_zoom(trab)
        return
    origem = trab / "cortado.mp4"
    if not origem.exists():
        raise SystemExit("falta o cortado.mp4: faça o corte antes")
    info = info_video(origem)
    dados_rosto = rastrear(origem, trab / "rosto.json")
    trilha = Trilha(dados_rosto)
    din = trab / "dinamica.json"
    eventos = [] if a.sem_zoom or not din.exists() else json.loads(din.read_text(encoding="utf-8")).get("eventos", [])
    # o vertical já é um recorte ampliado da webcam: zoom mais contido para não perder nitidez
    zoom = Zoom(eventos, 1.0 if a.formato == "horizontal" else 0.6)
    desfoque = Desfoque(ler_desfoque(trab))
    pasta = trab / a.formato
    pasta.mkdir(exist_ok=True)
    destino = pasta / "base.mp4"
    seguir = None if a.seguir == "auto" else a.seguir == "sim"

    if a.formato == "react":
        if not a.referencia:
            raise SystemExit("o formato react precisa de --referencia <vídeo>")
        layout = montar_react(trab, a, info, trilha, zoom, destino, desfoque)
    else:
        if a.formato == "vertical":
            ow, oh = 1080, 1920
        else:
            ow, oh = tamanho_horizontal(info)
        enq = Enquadrador(info["largura"], info["altura"], ow, oh, trilha, zoom, seguir=seguir, centro_x=a.centro_x)
        mesmo_quadro = abs(enq.bw - info["largura"]) < 2 and abs(enq.bh - info["altura"]) < 2
        if not zoom.ev and not desfoque and mesmo_quadro:
            reencodar_gop(origem, destino, info, ow, oh)
        else:
            renderizar_python(origem, destino, enq, info, desfoque=desfoque)
        rosto = enq.rosto_na_saida()
        layout = {"formato": a.formato, "largura": ow, "altura": oh,
                  "areas": {"voce": [0, 0, ow, oh]}, "costura": None,
                  "recorte": {"largura_origem": round(enq.bw), "segue_rosto": enq.seguir,
                              "rosto_fora_do_recorte_fixo": round(enq.fora, 3)},
                  "rosto": rosto,
                  "legenda": legenda_vertical(rosto, oh) if a.formato == "vertical"
                  else {"alinhamento": "baixo", "margem_v": int(oh * 0.08)}}

    layout["zooms"] = len(zoom.ev)
    layout["desfoques"] = len(desfoque)
    layout["sem_rosto"] = bool(dados_rosto.get("sem_rosto"))
    (pasta / "layout.json").write_text(json.dumps(layout, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"layout {a.formato}: {layout['largura']}x{layout['altura']}, {len(zoom.ev)} zooms, {len(desfoque)} desfoques → {destino}")
    if layout["sem_rosto"]:
        print("aviso: nenhum rosto detectado; enquadramento centralizado")


if __name__ == "__main__":
    main()
