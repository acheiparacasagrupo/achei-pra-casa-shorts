"""Gera o video-ponte "LINK CLIQUE AQUI": ensina a entrar no grupo VIP (9:16, voz + telas ilustradas).
Uso: python ponte.py  ->  out/ponte.mp4"""
import asyncio, math, os, subprocess
from PIL import Image, ImageDraw, ImageFilter

W, H, FPS = 1080, 1920, 30
AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.getcwd(), "out")
FONTE = os.path.join(AQUI, "Poppins-Bold.ttf")
from PIL import ImageFont
F = lambda s: ImageFont.truetype(FONTE, s)
ROSA, AMARELO, ESCURO, BRANCO, VERDE = (255, 90, 122), (255, 210, 63), (30, 30, 46), (255, 255, 255), (37, 211, 102)
VOZ = os.environ.get("VOZ", "pt-BR-FranciscaNeural")
LINK = os.environ.get("LINK_CURTO", "moraesb02.github.io/achei-pra-casa-shorts/grupo")
PERFIL = Image.open(os.path.join(AQUI, "perfil.png")).convert("RGBA")
CAPA = Image.open(os.path.join(AQUI, "capa.png")).convert("RGB")


def circulo(img, d):
    im = img.resize((d, d), Image.LANCZOS)
    m = Image.new("L", (d, d), 0); ImageDraw.Draw(m).ellipse([0, 0, d - 1, d - 1], fill=255)
    im.putalpha(m); return im


def texto_centro(d, y, txt, f, cor, contorno=ESCURO, sw=6, larg=W - 120):
    linhas, atual = [], ""
    for p in txt.split():
        t = (atual + " " + p).strip()
        if d.textlength(t, font=f) <= larg: atual = t
        else: linhas.append(atual); atual = p
    linhas.append(atual)
    for i, l in enumerate(linhas):
        d.text((W / 2, y + i * f.size * 1.2), l, font=f, fill=cor, anchor="mm", stroke_width=sw, stroke_fill=contorno)


# ---------- telas ----------
def tela_intro():
    im = Image.new("RGB", (W, H), (255, 246, 236)); d = ImageDraw.Draw(im)
    capa = CAPA.resize((W, int(W * CAPA.height / CAPA.width)))
    im.paste(capa, (0, 300))
    texto_centro(d, 1150, "QUER O LINK DOS PRODUTOS COM DESCONTO?", F(86), AMARELO)
    return im, None


def tela_short():
    im = Image.new("RGB", (W, H), (20, 20, 24)); d = ImageDraw.Draw(im)
    # "video" de fundo
    d.rounded_rectangle([60, 160, W - 60, 1500], 40, fill=(70, 60, 55))
    for i in range(6):
        d.rounded_rectangle([200 + i * 20, 500 + i * 60, 880 - i * 20, 540 + i * 60], 12, fill=(160, 120, 80))
    # coluna da direita
    for i, y in enumerate([900, 1050, 1200, 1350]):
        d.ellipse([W - 175, y, W - 85, y + 90], fill=(60, 60, 66))
    # rodape do short
    av = circulo(PERFIL, 110); im.paste(av, (80, 1560), av)
    d.text((215, 1615), "@acheipracasaoficial", font=F(40), fill=BRANCO, anchor="lm")
    d.text((80, 1720), "PARE DE SOFRER COM O BANHEIRO...", font=F(40), fill=BRANCO, anchor="lm")
    d.rounded_rectangle([80, 1780, 560, 1850], 35, fill=(55, 55, 60))
    d.text((110, 1815), "> LINK CLIQUE AQUI", font=F(36), fill=BRANCO, anchor="lm")
    return im, (135, 1615, 85)


def tela_canal():
    im = Image.new("RGB", (W, H), (15, 15, 15)); d = ImageDraw.Draw(im)
    capa = CAPA.resize((W - 80, int((W - 80) * 9 / 16)))
    capa = capa.crop((0, int(capa.height * 0.3), capa.width, int(capa.height * 0.7)))
    im.paste(capa, (40, 160))
    av = circulo(PERFIL, 220); im.paste(av, (60, 520), av)
    d.text((310, 580), "Achei pra Casa", font=F(64), fill=BRANCO, anchor="lm")
    d.text((310, 670), "@acheipracasaoficial", font=F(38), fill=(200, 200, 200), anchor="lm")
    d.text((60, 830), "LINK DO GRUPO VIP ABAIXO", font=F(44), fill=BRANCO, anchor="lm")
    d.text((60, 920), LINK, font=F(30), fill=(62, 166, 255), anchor="lm")
    d.text((60, 975), "e mais 1 link", font=F(32), fill=(170, 170, 170), anchor="lm")
    d.rounded_rectangle([60, 1060, 420, 1150], 45, fill=BRANCO)
    d.text((240, 1105), "Inscrever-se", font=F(40), fill=ESCURO, anchor="mm")
    return im, (420, 920, 120)


def tela_whats():
    im = Image.new("RGB", (W, H), (11, 20, 26)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([90, 420, W - 90, 1420], 50, fill=(32, 44, 51))
    av = circulo(PERFIL, 260); im.paste(av, ((W - 260) // 2, 500), av)
    texto_centro(d, 860, "Achei pra Casa - Achadinhos VIP", F(50), BRANCO, (32, 44, 51), 0, W - 260)
    d.text((W / 2, 1010), "Grupo do WhatsApp", font=F(36), fill=(170, 180, 185), anchor="mm")
    d.rounded_rectangle([200, 1150, W - 200, 1270], 60, fill=VERDE)
    d.text((W / 2, 1210), "Entrar no grupo", font=F(50), fill=(11, 20, 26), anchor="mm")
    return im, (W // 2, 1210, 330)


def tela_final():
    im = Image.new("RGB", (W, H), ROSA); d = ImageDraw.Draw(im)
    av = circulo(PERFIL, 380); im.paste(av, ((W - 380) // 2, 380), av)
    texto_centro(d, 950, "ACHADINHOS COM CUPOM TODO DIA", F(84), AMARELO)
    texto_centro(d, 1300, "O link tambem esta na descricao deste video", F(48), BRANCO, (170, 30, 70), 4)
    return im, None


CENAS = [
    (tela_intro, "Quer o link de todos os produtos com desconto? É bem fácil, olha só."),
    (tela_short, "No vídeo que você estava assistindo, toque na foto do canal, essa rosinha com a casinha."),
    (tela_canal, "Lá no topo do canal, toque no link do grupo VIP, logo abaixo do nome."),
    (tela_whats, "Pronto! É só tocar em entrar no grupo. Lá tem todos os achadinhos que a gente posta, com cupom de desconto todos os dias."),
    (tela_short, "Repetindo: toque na foto do canal,"),
    (tela_canal, "depois no link do grupo VIP,"),
    (tela_whats, "e entre no grupo. Te espero lá!"),
    (tela_final, "E se preferir, o link também está aqui na descrição."),
]


async def falar(txt, mp3):
    import edge_tts
    await edge_tts.Communicate(txt, VOZ, rate="+5%").save(mp3)


def dur(a):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a],
                                capture_output=True, text=True).stdout.strip())


def main():
    os.makedirs(OUT, exist_ok=True)
    audios, tempos = [], []
    for i, (_, txt) in enumerate(CENAS):
        a = os.path.join(OUT, f"p{i}.mp3")
        try:
            asyncio.run(falar(txt, a))
        except Exception as e:
            if os.environ.get("CI"): raise
            print("TTS indisponivel (teste local):", e)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                            "-t", f"{0.4 * len(txt.split()) + 0.5:.2f}", "-c:a", "libmp3lame", a], check=True)
        audios.append(a); tempos.append(dur(a) + 0.35)
    lista = os.path.join(OUT, "lista.txt")
    with open(lista, "w") as f:
        for a, t in zip(audios, tempos):
            f.write(f"file '{a}'\nduration {t:.3f}\n")
    voz = os.path.join(OUT, "ponte_voz.m4a")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lista,
                    "-af", "apad", "-t", f"{sum(tempos):.2f}", "-c:a", "aac", voz], check=True)

    saida = os.path.join(OUT, "ponte.mp4")
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", voz, "-map", "0:v", "-map", "1:a",
                             "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
                             "-c:a", "aac", "-shortest", "-movflags", "+faststart", saida], stdin=subprocess.PIPE)
    legenda_f = F(60)
    for (fn, txt), t in zip(CENAS, tempos):
        base, alvo = fn()
        n = int(t * FPS)
        for k in range(n):
            fr = base.copy(); d = ImageDraw.Draw(fr)
            if alvo:
                x, y, r = alvo
                pulso = r + 18 * (1 + math.sin(k / FPS * 2 * math.pi * 1.5)) / 2
                d.ellipse([x - pulso, y - pulso * 0.6 if r > 200 else y - pulso, x + pulso,
                           y + pulso * 0.6 if r > 200 else y + pulso], outline=AMARELO, width=12)
                # seta apontando
                ay = y - (pulso * 0.6 if r > 200 else pulso) - 30
                d.polygon([(x - 45, ay - 80), (x + 45, ay - 80), (x, ay)], fill=AMARELO, outline=ESCURO, width=5)
            # legenda da fala
            d.rounded_rectangle([40, 40, W - 40, 150], 30, fill=(30, 30, 46))
            d.text((W / 2, 95), "COMO ENTRAR NO GRUPO VIP", font=F(52), fill=AMARELO, anchor="mm")
            linhas, atual = [], ""
            for p in txt.split():
                tt = (atual + " " + p).strip()
                if d.textlength(tt, font=legenda_f) <= W - 140: atual = tt
                else: linhas.append(atual); atual = p
            linhas.append(atual)
            y0 = 1690 - (len(linhas) - 1) * 38 if fn in (tela_canal, tela_whats, tela_intro, tela_final) else 1300
            if fn is tela_short:
                y0 = 330
            for i, l in enumerate(linhas):
                d.text((W / 2, y0 + i * 76), l, font=legenda_f, fill=BRANCO, anchor="mm", stroke_width=7, stroke_fill=ESCURO)
            proc.stdin.write(fr.tobytes())
    proc.stdin.close(); proc.wait()
    print("OK", saida, round(dur(saida), 1), "s")


if __name__ == "__main__":
    main()
