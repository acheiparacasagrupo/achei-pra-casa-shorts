"""
buscar_produto.py v4 — scraping real do Mercado Livre (sem API)
- Gemini gera conceito/query do produto
- Scraping do SITE ML (nao da API, que e bloqueada) para achar produto real
- Extrai: link real do produto, imagens da galeria ML, video do vendedor
- proximo.py ja prioriza linhas com 'videos' preenchido
- run.py/render.py ja usam 'videos' para background do Short
"""
import json, os, random, re, sys, requests
from google import genai
import gspread
from google.oauth2.service_account import Credentials

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_CREDENTIALS_JSON = os.environ["GOOGLE_CREDENTIALS"]
PLANILHA_ID = os.environ.get("PLANILHA_ID", "1DEXtunlKTCBKu3lmYYPLp8X0nsuSNaRe8CaSLdExLbU")

COMODOS = ["cozinha", "banheiro", "limpeza", "decoracao", "organizacao"]

FALLBACK_PRODUTOS = {
    "cozinha": {"nome": "Organizador de Talheres Bambu 3 Divisoes", "preco": 39.90,
                "detalhes": "Organiza talheres de vez. Bambu resistente, encaixa em qualquer gaveta. Chega de baguncia.",
                "query": "organizador talheres bambu cozinha"},
    "banheiro": {"nome": "Suporte Shampoo Inox Adesivo Sem Furo", "preco": 28.90,
                 "detalhes": "Fixa sem furar a parede. Inox resistente, aguenta shampoo, condicionador e sabonete.",
                 "query": "suporte shampoo inox sem furo banheiro"},
    "limpeza": {"nome": "Rodo Magico Giratorio Mop 360 Graus", "preco": 59.90,
                "detalhes": "Limpa o chao sem dobrar as costas. Gira 360 graus e escorre sozinho. Sensacao de casa limpa.",
                "query": "rodo magico giratorio mop limpeza"},
    "decoracao": {"nome": "Luminaria LED Touch Recarregavel USB", "preco": 45.90,
                  "detalhes": "Ilumina qualquer ambiente sem fio. Tres tons de luz, toque para ligar. Perfeita para cabeceira.",
                  "query": "luminaria led touch recarregavel usb"},
    "organizacao": {"nome": "Caixa Organizadora Dobravel com Tampa", "preco": 34.90,
                    "detalhes": "Dobra quando nao usa, abre quando precisa. Ideal para roupas, brinquedos ou objetos.",
                    "query": "caixa organizadora dobravel com tampa"},
}

ML_HDRS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI: gera conceito do produto
# ─────────────────────────────────────────────────────────────────────────────

def _gemini(prompt: str) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return resp.text.strip()


def gerar_conceito(comodo: str) -> dict:
    """Gemini gera conceito + query de busca para o produto."""
    try:
        r = _gemini(
            "Voce e especialista em produtos virais para casa no Brasil.\n\n"
            f"Gere 1 produto viral para o comodo: {comodo}\n\n"
            "Criterios:\n"
            "- Preco entre R$15 e R$120\n"
            "- Gadget/achadinho que viraliza no TikTok e Reels\n"
            "- Produto real, muito vendido no Brasil no Mercado Livre\n"
            "- Resolve uma dor real do dia a dia\n\n"
            "Retorne APENAS JSON valido (sem markdown, sem explicacoes):\n"
            '{"nome": "nome do produto (max 80 chars)", "preco": 49.90, '
            '"detalhes": "descricao atrativa max 180 chars sem emojis", '
            '"query": "3-5 palavras de busca em portugues para buscar no ML"}'
        )
        r = re.sub(r"```\w*\s*", "", r).strip()
        if r.startswith("```"):
            r = r[3:]
        if r.endswith("```"):
            r = r[:-3]
        dados = json.loads(r.strip())
        print(f"  Gemini conceito: {str(dados.get('nome', ''))[:60]}")
        return dados
    except Exception as e:
        print(f"  Gemini falhou ({e}), usando fallback")
        return dict(FALLBACK_PRODUTOS.get(comodo, FALLBACK_PRODUTOS["cozinha"]))


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPING ML: achar produto real, imagens e video
# ─────────────────────────────────────────────────────────────────────────────

def _find_in_json(obj, keys, depth=0):
    """Busca recursiva por chaves num objeto JSON aninhado."""
    if depth > 10 or obj is None:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k]:
                return obj[k]
        for v in obj.values():
            r = _find_in_json(v, keys, depth + 1)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for item in obj:
            r = _find_in_json(item, keys, depth + 1)
            if r is not None:
                return r
    return None


def _extrair_galeria(obj, depth=0):
    """Encontra lista de fotos/videos na estrutura JSON do ML."""
    if depth > 10 or not isinstance(obj, (dict, list)):
        return []
    if isinstance(obj, list):
        # Lista com itens que tenham 'type' ou 'url' = pode ser galeria
        if len(obj) >= 1 and isinstance(obj[0], dict):
            if any(k in obj[0] for k in ("type", "url", "secure_url", "id")):
                return obj
        for item in obj:
            r = _extrair_galeria(item, depth + 1)
            if r:
                return r
        return []
    # dict
    for chave in ("pictures", "gallery", "components"):
        if chave in obj:
            r = _extrair_galeria(obj[chave], depth + 1)
            if r:
                return r
    for v in obj.values():
        r = _extrair_galeria(v, depth + 1)
        if r:
            return r
    return []


def buscar_no_ml(query: str) -> dict:
    """
    Scrapa o SITE mercadolivre.com.br (nao a API) para achar produto real.
    Retorna: link, imagens[], videos[], nome, preco
    """
    vazio = {"link": None, "imagens": [], "videos": [], "nome": "", "preco": 0.0}

    try:
        # ── 1. Página de busca do ML ──────────────────────────────────────
        q = requests.utils.quote(query, safe="")
        print(f"  Scraping ML: {query}")
        r = requests.get(
            f"https://www.mercadolivre.com.br/jm/search?as_word={q}&site_id=MLB",
            headers=ML_HDRS, timeout=25, allow_redirects=True
        )
        if r.status_code != 200:
            print(f"  ML busca HTTP {r.status_code}")
            return vazio

        html = r.text
        produto_url = None

        # Padrao A: "permalink" no JSON da pagina de busca
        perma = re.findall(
            r'"permalink"\s*:\s*"(https://www\.mercadolivre\.com\.br/[^"]+)"', html
        )
        if perma:
            produto_url = perma[0].split("?")[0]

        # Padrao B: href com MLB- (produto individual)
        if not produto_url:
            for h in re.findall(r'href="(https://www\.mercadolivre\.com\.br/[^"?#]+)"', html):
                if re.search(r'-MLB-\d+|/MLB\d+', h):
                    produto_url = h.split("?")[0]
                    break

        if not produto_url:
            print("  Nenhum produto encontrado na busca")
            return vazio

        print(f"  Produto: {produto_url[:90]}")
        resultado = dict(vazio)
        resultado["link"] = produto_url

        # ── 2. Página do produto ──────────────────────────────────────────
        r2 = requests.get(produto_url, headers=ML_HDRS, timeout=25, allow_redirects=True)
        if r2.status_code != 200:
            print(f"  Pagina produto HTTP {r2.status_code}")
            return resultado

        html2 = r2.text

        # ── 3. Extrair __NEXT_DATA__ ──────────────────────────────────────
        nd_match = re.search(
            r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>([\s\S]+?)</script>', html2
        )
        if nd_match:
            try:
                nd = json.loads(nd_match.group(1))
                state = (
                    nd.get("props", {}).get("pageProps", {}).get("initialState", {})
                    or nd.get("props", {}).get("pageProps", {})
                    or nd
                )

                # Nome do produto
                nome = _find_in_json(state, ["title"])
                if nome and isinstance(nome, str) and len(nome) > 5:
                    resultado["nome"] = nome[:100]

                # Preco
                preco = _find_in_json(state, ["price"])
                if preco and isinstance(preco, (int, float)):
                    resultado["preco"] = float(preco)

                # Galeria de fotos e videos
                galeria = _extrair_galeria(state)
                for item in galeria:
                    if not isinstance(item, dict):
                        continue
                    tipo = str(item.get("type", "")).lower()
                    if "video" in tipo:
                        vurl = (item.get("url") or item.get("videoUrl")
                                or item.get("video_url") or "")
                        if vurl and isinstance(vurl, str) and len(vurl) > 10:
                            resultado["videos"].append(vurl)
                    else:
                        iurl = (item.get("url") or item.get("secure_url") or
                                item.get("max_size") or "")
                        if iurl and "mlstatic.com" in iurl:
                            # Versao HD: trocar sufixo de thumb por -O (original)
                            iurl_hd = re.sub(r'-[A-Z]\.(jpg|jpeg|webp)$', r'-O.jpg', iurl)
                            resultado["imagens"].append(iurl_hd)

            except Exception as e:
                print(f"  NEXT_DATA parse: {e}")

        # ── 4. Fallback regex: imagens mlstatic ──────────────────────────
        if not resultado["imagens"]:
            imgs_raw = re.findall(
                r'"(https://http2\.mlstatic\.com/D_NQ_NP_[^"]+\.(?:jpg|jpeg|webp))"',
                html2
            )
            imgs_hd = [re.sub(r'-[A-Z]\.(jpg|jpeg|webp)$', r'-O.jpg', u) for u in imgs_raw]
            resultado["imagens"] = list(dict.fromkeys(imgs_hd))[:4]

        # ── 5. Fallback regex: og:image ───────────────────────────────────
        if not resultado["imagens"]:
            og = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                html2
            )
            if og:
                resultado["imagens"] = [og.group(1)]

        # ── 6. Fallback regex: videos mp4 ────────────────────────────────
        if not resultado["videos"]:
            for pat in [
                r'"videoUrl"\s*:\s*"([^"]+\.mp4[^"]*)"',
                r'"video_url"\s*:\s*"([^"]+\.mp4[^"]*)"',
                r'"url"\s*:\s*"(https://[^"]+(?:mlstatic|video)[^"]+\.mp4[^"]*)"',
                r'src=["\']([^"\']+\.mp4[^"\']*)["\']',
            ]:
                vids = re.findall(pat, html2)
                if vids:
                    resultado["videos"] = vids[:2]
                    break

        print(
            f"  ML resultado -> {len(resultado['imagens'])} img | "
            f"{len(resultado['videos'])} vid | "
            f"link: {bool(resultado['link'])}"
        )
        return resultado

    except Exception as e:
        print(f"  ML scraping erro: {e}")
        return vazio


# ─────────────────────────────────────────────────────────────────────────────
# IMAGEM FALLBACK: Unsplash (sem API key, imagens reais)
# ─────────────────────────────────────────────────────────────────────────────

def buscar_imagem_fallback(query: str) -> str:
    """Tenta Unsplash Source antes do placeholder laranja."""
    kw = query[:60].replace(" ", ",")
    for url in [
        f"https://source.unsplash.com/800x800/?{kw}",
        f"https://loremflickr.com/800/800/{kw}",
    ]:
        try:
            resp = requests.get(
                url, timeout=15, allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code == 200 and resp.url.startswith("https://"):
                print(f"  Imagem fallback: {resp.url[:70]}")
                return resp.url
        except Exception as e:
            print(f"  {url[:40]} falhou: {e}")
    kw2 = query[:30].replace(" ", "+")
    return f"https://placehold.co/800x800/4A90D9/FFFFFF/png?text={kw2}"


# ─────────────────────────────────────────────────────────────────────────────
# PLANILHA
# ─────────────────────────────────────────────────────────────────────────────

def inserir_planilha(produto: dict):
    """Insere produto com link real, imagens e video na planilha."""
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_CREDENTIALS_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    ws = gspread.authorize(creds).open_by_key(PLANILHA_ID).sheet1

    # Imagens: string separada por virgula
    imagens = produto.get("imagens") or []
    if isinstance(imagens, str):
        imagens = [imagens]
    imagens_str = ",".join(imagens[:3])

    # Videos: string separada por virgula (col K = 'videos')
    videos = produto.get("videos") or []
    if isinstance(videos, str):
        videos = [videos]
    videos_str = ",".join(videos[:2])

    # Link real do produto (nao URL de busca)
    link = produto.get("link") or (
        "https://www.mercadolivre.com.br/busca?q="
        + produto.get("query", produto["nome"]).replace(" ", "+")
    )

    ws.append_row(
        [
            "pendente",                    # A: status
            produto["nome"],               # B: nome
            produto.get("comodo", "casa"), # C: comodo
            produto["preco"],              # D: preco
            link,                          # E: link_afiliado (URL real do produto)
            imagens_str,                   # F: imagens
            produto.get("detalhes", ""),   # G: detalhes
            "",                            # H: titulo (gerado pelo run.py via Gemini)
            "",                            # I: video_id
            "",                            # J: data_postagem
            videos_str,                    # K: videos (URL video real do produto)
        ],
        value_input_option="USER_ENTERED",
    )
    print(
        f"Inserido: {produto['nome'][:50]} R${float(produto['preco']):.2f} | "
        f"link_real={bool(produto.get('link'))} | video={bool(videos_str)}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    comodo = random.choice(COMODOS)
    print(f"=== Gerando produto para: {comodo} ===")

    # 1. Gemini gera conceito e query de busca
    conceito = gerar_conceito(comodo)
    conceito["comodo"] = comodo

    # 2. Scraping do ML para dados reais
    ml = buscar_no_ml(conceito.get("query", conceito["nome"]))

    # 3. Merge: ML tem prioridade, Gemini como fallback
    produto = {
        "nome": ml.get("nome") or conceito["nome"],
        "preco": ml.get("preco") or conceito["preco"],
        "detalhes": conceito["detalhes"],  # Gemini sempre gera descricao atrativa
        "query": conceito.get("query", ""),
        "comodo": comodo,
        "link": ml.get("link"),
        "imagens": ml.get("imagens") or [],
        "videos": ml.get("videos") or [],
    }

    # 4. Fallback de imagem se ML nao trouxe nada
    if not produto["imagens"]:
        img = buscar_imagem_fallback(conceito.get("query", conceito["nome"]))
        produto["imagens"] = [img]

    # Inserir na planilha
    inserir_planilha(produto)
    print(f"=== Concluido: video_real={bool(produto['videos'])} ===")


if __name__ == "__main__":
    main()
