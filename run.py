"""Pipeline completo: dados do produto -> textos (Gemini) -> voz (edge-tts) -> video -> out/meta.json
Uso: python run.py payload.json"""
import asyncio, json, os, subprocess, sys
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textos, render

VOZ = os.environ.get("VOZ", "pt-BR-FranciscaNeural")
OUT = os.path.join(os.getcwd(), "out")


async def narrar(frases, mp3):
    import edge_tts
    texto = " ".join(frases)
    com = edge_tts.Communicate(texto, VOZ, rate="+10%", boundary="WordBoundary")
    palavras = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                ini = ch["offset"] / 1e7
                palavras.append((ini, ini + ch["duration"] / 1e7, ch["text"]))
    return palavras


def duracao(arq):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", arq],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def narracao_muda(frases, mp3):
    """So para teste local sem internet: audio mudo com tempos estimados."""
    palavras, t = [], 0.3
    for p in " ".join(frases).split():
        d = 0.28 + 0.02 * len(p)
        palavras.append((t, t + d, p)); t += d
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", f"{t + 0.3:.2f}", "-c:a", "libmp3lame", mp3], check=True)
    return palavras


def baixar_imagens(urls, pasta):
    caminhos = []
    for i, u in enumerate([u.strip() for u in urls if u.strip()][:6]):
        try:
            if os.path.exists(u):
                caminhos.append(u); continue
            r = requests.get(u, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            p = os.path.join(pasta, f"img{i}.jpg")
            open(p, "wb").write(r.content)
            from PIL import Image
            Image.open(p).verify()
            caminhos.append(p)
        except Exception as e:
            print("imagem ignorada:", u, e)
    if not caminhos:
        raise SystemExit("Nenhuma imagem valida para o produto.")
    return caminhos


def main():
    payload = json.load(open(sys.argv[1]))
    os.makedirs(OUT, exist_ok=True)
    imgs = payload.get("imagens", "")
    imgs = imgs if isinstance(imgs, list) else imgs.replace("\n", ",").split(",")

    t = textos.gerar(payload)
    print(json.dumps(t, ensure_ascii=False, indent=2))

    mp3 = os.path.join(OUT, "voz.mp3")
    try:
        palavras = asyncio.run(narrar(t["narracao"], mp3))
    except Exception as e:
        if os.environ.get("CI"):
            raise
        print("TTS indisponivel, usando audio mudo:", e)
        palavras = narracao_muda(t["narracao"], mp3)

    fotos = baixar_imagens(imgs, OUT)
    video = os.path.join(OUT, "video.mp4")
    render.render(fotos, mp3, palavras, t["gancho"], str(payload.get("preco") or "").strip(),
                  video, duracao(mp3))

    meta = {"row_id": str(payload.get("row_id", "")), "titulo": t["titulo"], "descricao": t["descricao"],
            "tags": t["tags"], "comodo": t["comodo"], "playlist_id": t["playlist_id"], "gancho": t["gancho"],
            "duracao": round(duracao(video), 1)}
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), ensure_ascii=False)
    print("OK", video, meta["duracao"], "s")


if __name__ == "__main__":
    main()
