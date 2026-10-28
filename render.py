"""Monta o Short 9:16 (1080x1920) com Pillow + FFmpeg.
Camadas: fundo desfocado, foto do produto com zoom lento, gancho no topo,
legendas palavra a palavra, selo de preco e CTA final para o grupo VIP."""
import math, os, subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
AQUI = os.path.dirname(os.path.abspath(__file__))
FONTE = os.path.join(AQUI, "Poppins-Bold.ttf")
AMARELO, ROSA, ESCURO, BRANCO = (255, 210, 63), (255, 90, 122), (30, 30, 46), (255, 255, 255)
HANDLE = os.environ.get("HANDLE_CANAL", "@acheipracasaoficial")


def fonte(t):
    return ImageFont.truetype(FONTE, t)


def quebra(texto, f, largura, d):
    linhas, atual = [], ""
    for p in texto.split():
        teste = (atual + " " + p).strip()
        if d.textlength(teste, font=f) <= largura:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def cobrir(img, w, h):
    r = max(w / img.width, h / img.height)
    im = img.resize((int(img.width * r) + 1, int(img.height * r) + 1), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def caixa_arredondada(img, raio):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, img.width - 1, img.height - 1], raio, fill=255)
    out = img.convert("RGBA"); out.putalpha(m)
    return out


def camada_gancho(gancho):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    tam = 86
    while True:
        f = fonte(tam); linhas = quebra(gancho, f, W - 140, d)
        if len(linhas) <= 3 or tam <= 56:
            break
        tam -= 6
    alt = len(linhas) * int(tam * 1.18)
    y0 = 150
    d.rounded_rectangle([40, y0 - 30, W - 40, y0 + alt + 30], 40, fill=(30, 30, 46, 215))
    for i, l in enumerate(linhas):
        d.text((W / 2, y0 + i * int(tam * 1.18) + tam * 0.55), l, font=f, fill=AMARELO,
               anchor="mm", stroke_width=6, stroke_fill=ESCURO)
    f2 = fonte(34)
    d.text((W / 2, 1580), HANDLE, font=f2, fill=BRANCO, anchor="mm", stroke_width=4, stroke_fill=ESCURO)
    return lay


def camada_preco(preco):
    if not preco:
        return None
    lay = Image.new("RGBA", (420, 150), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, 419, 149], 36, fill=ROSA)
    txt = preco if preco.lower().startswith("r$") else f"R$ {preco}"
    d.text((210, 48), "SÓ", font=fonte(36), fill=BRANCO, anchor="mm")
    d.text((210, 102), txt, font=fonte(58), fill=BRANCO, anchor="mm", stroke_width=3, stroke_fill=(180, 40, 80))
    return lay.rotate(6, expand=True, resample=Image.BICUBIC)


def camada_cta():
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    y = 1120
    d.rounded_rectangle([70, y, W - 70, y + 300], 50, fill=ROSA + (240,))
    d.text((W / 2, y + 85), "LINK COM DESCONTO", font=fonte(70), fill=BRANCO, anchor="mm",
           stroke_width=4, stroke_fill=(170, 30, 70))
    d.text((W / 2, y + 175), "NO GRUPO VIP", font=fonte(70), fill=AMARELO, anchor="mm",
           stroke_width=5, stroke_fill=ESCURO)
    d.text((W / 2, y + 255), "toque em LINK CLIQUE AQUI", font=fonte(40), fill=BRANCO, anchor="mm")
    # seta para baixo
    cx, cy = W / 2, y + 370
    d.polygon([(cx - 70, cy - 40), (cx + 70, cy - 40), (cx, cy + 50)], fill=AMARELO, outline=ESCURO, width=6)
    return lay


def grupos_legenda(palavras, max_p=3):
    """palavras: lista (inicio, fim, texto). Agrupa em blocos de ate 3 palavras."""
    grupos, atual = [], []
    for p in palavras:
        atual.append(p)
        if len(atual) >= max_p or p[2].endswith((".", "!", "?", ",")):
            grupos.append(atual); atual = []
    if atual:
        grupos.append(atual)
    return grupos


def desenha_legenda(base, grupo, t):
    d = ImageDraw.Draw(base)
    f = fonte(88)
    textos = [g[2].upper() for g in grupo]
    linhas = quebra(" ".join(textos), f, W - 120, d)
    y = 1330 - (len(linhas) - 1) * 55
    idx = 0
    for linha in linhas:
        ps = linha.split()
        larg = d.textlength(linha, font=f)
        x = (W - larg) / 2
        for p in ps:
            ativo = idx < len(grupo) and grupo[idx][0] <= t < grupo[idx][1] + 0.05
            d.text((x, y), p, font=f, fill=AMARELO if ativo else BRANCO, anchor="lm",
                   stroke_width=9, stroke_fill=ESCURO)
            x += d.textlength(p + " ", font=f); idx += 1
        y += 110


def render(imagens, audio, palavras, gancho, preco, saida, duracao_audio):
    total = duracao_audio + 0.7
    n_frames = int(total * FPS)
    fotos = [Image.open(p).convert("RGB") for p in imagens] or [Image.new("RGB", (800, 800), (240, 200, 210))]
    fundos = [cobrir(f, W, H).filter(ImageFilter.GaussianBlur(38)).point(lambda v: int(v * 0.55)) for f in fotos]
    frente = []
    for f in fotos:
        r = min(960 / f.width, 860 / f.height)
        frente.append(caixa_arredondada(f.resize((int(f.width * r), int(f.height * r)), Image.LANCZOS), 40))
    gancho_l = camada_gancho(gancho); cta_l = camada_cta(); preco_l = camada_preco(preco)
    grupos = grupos_legenda(palavras)
    inicio_cta = max(total - 3.6, total * 0.7)
    seg = total / len(fotos)

    proc = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-i", audio,
        *(["-stream_loop", "-1", "-i", os.environ["MUSICA"]] if os.environ.get("MUSICA") else []),
        "-filter_complex",
        ("[1:a]apad,volume=1.0[v];[2:a]volume=0.10[m];[v][m]amix=inputs=2:duration=first[a]"
         if os.environ.get("MUSICA") else "[1:a]apad[a]"),
        "-map", "0:v", "-map", "[a]", "-t", f"{n_frames / FPS:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", saida,
    ], stdin=subprocess.PIPE)

    for i in range(n_frames):
        t = i / FPS
        k = min(int(t / seg), len(fotos) - 1)
        prog = (t - k * seg) / seg
        frame = fundos[k].copy()
        fr = frente[k]
        esc = 1.0 + 0.08 * prog
        im = fr.resize((int(fr.width * esc), int(fr.height * esc)), Image.BILINEAR)
        # entrada com leve "pop" nos primeiros 0,25s de cada foto
        if t - k * seg < 0.25:
            s = 0.85 + 0.15 * ((t - k * seg) / 0.25)
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
        frame.paste(im, ((W - im.width) // 2, 800 - im.height // 2), im)
        frame.paste(gancho_l, (0, 0), gancho_l)
        if preco_l is not None and t > 1.0:
            frame.paste(preco_l, (W - preco_l.width - 30, 470), preco_l)
        if t >= inicio_cta:
            a = min(1.0, (t - inicio_cta) / 0.3)
            c = cta_l if a >= 1 else Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 0)), cta_l, a)
            frame.paste(c, (0, 0), c)
        else:
            atual = next((g for g in grupos if g[0][0] - 0.05 <= t <= g[-1][1] + 0.15), None)
            if atual:
                desenha_legenda(frame, atual, t)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg falhou")
