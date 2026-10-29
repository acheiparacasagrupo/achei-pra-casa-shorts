"""Gera titulo, narracao, descricao e tags do Short com o Gemini (plano gratuito).
Se nao houver chave ou a API falhar, usa um modelo de texto pronto."""
import json, os, random, re, requests

GRUPO = os.environ.get("LINK_GRUPO", "https://acheiparacasagrupo.github.io/achei-pra-casa-shorts/grupo/")
# Hashtags amplas do nicho (sempre presentes, poucas e fortes)
HASH_NICHO = []
PLAYLISTS = {
    "cozinha": "PLZDnLFzStzYQ",
    "banheiro": "PLXg5SUpFX7Do",
    "organizacao": "PLG7M7_pm1_Fs",hh
    "limpeza": "PLGJvMq4wDZGo",
    "decoracao": "PLeB85ZROaMEE",
}
HASH_COMODO = {
    "cozinha": ["#cozinha", "#cozinhaorganizada"],
    "banheiro": ["#banheiro", "#banheiroorganizado"],
    "organizacao": ["#organizacao", "#casaorganizada"],
    "limpeza": ["#limpeza", "#dicasdelimpeza"],
    "decoracao": ["#decoracao", "#decoracaobarata"],
}

PROMPT = """Voce e roteirista e especialista em SEO de YouTube Shorts de um canal brasileiro chamado "Achei pra Casa", que mostra achadinhos baratos para casa e leva o publico para um grupo VIP de ofertas no WhatsApp.

Produto: {nome}
Comodo: {comodo}
Preco (pode estar vazio): {preco}
Detalhes (pode estar vazio): {detalhes}

Pense primeiro: quem compra esse produto, qual problema ele resolve, e COMO essa pessoa pesquisaria no YouTube/Google (termo popular, nao o nome tecnico do anuncio). Depois crie o texto de UM Short de 20 a 28 segundos. Regras:

- "palavra_chave": como o brasileiro pesquisa esse produto, 2 a 4 palavras, minusculas (ex: "escova eletrica de limpeza", "porta tempero giratorio", "luminaria com sensor").
- "gancho": titulo em CAIXA ALTA, no maximo 50 caracteres, focado no BENEFICIO, na DOR resolvida ou na CURIOSIDADE. Pode citar o tipo de produto se isso deixar o titulo mais pesquisavel, mas nunca a marca nem o nome longo do anuncio. Formulas que funcionam no nicho: "O DETALHE QUE FALTAVA NA SUA COZINHA", "PARE DE SOFRER PRA LIMPAR O BOX", "EU NAO SABIA QUE PRECISAVA DISSO", "ESSA ESCOVA LIMPA O REJUNTE SOZINHA", "QUEM TEM CASA PEQUENA PRECISA VER ISSO". Sem emoji, sem hashtag, acentuacao correta.
- "nome_curto": nome popular e curto do produto, 2 a 4 palavras, em CAIXA ALTA (ex: "ESCOVA ELETRICA 9 EM 1", "KIT CABECEIRA", "LUMINARIA COM SENSOR").
- "narracao": lista de 4 a 6 frases curtas, faladas, tom animado e natural de amiga indicando um achado, total entre 55 e 75 palavras. Frase 1 = gancho forte que prende nos 2 primeiros segundos. Frases do meio = o problema que resolve e 2 beneficios concretos tirados dos detalhes. Ultima frase = CTA com a ideia: "Se voce quiser receber estes produtos com desconto para casa todos os dias, basta clicar no nome deste canal do YouTube e na bio do canal clicar no link para o WhatsApp." Nao invente preco nem medidas que nao foram informadas. Sem emojis.
- "descricao": 2 frases vendedoras; a PRIMEIRA frase deve conter a palavra_chave de forma natural (SEO). Pode ter 1 ou 2 emojis.
- "tags": 12 palavras-chave de busca, minusculas, sem #: variacoes da palavra_chave, o problema resolvido (ex: "como limpar rejunte"), o comodo e 2 termos do nicho ("achadinhos para casa", "achadinhos shopee").

Responda SOMENTE com JSON: {{"palavra_chave": "...", "gancho": "...", "nome_curto": "...", "narracao": ["..."], "descricao": "...", "tags": ["..."]}}"""


def _gemini(prod):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    modelos = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-flash-latest", "gemini-2.5-flash",
               "gemini-2.0-flash", "gemini-flash-lite-latest"] if m]
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(**prod)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
    }
    for model in modelos:
        for _ in range(2):
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": key}, json=body, timeout=60)
                if r.status_code == 404:
                    print("Modelo indisponivel:", model)
                    break
                r.raise_for_status()
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(txt)
                if data.get("gancho") and data.get("narracao"):
                    print("Texto gerado pelo", model)
                    return data
            except Exception as e:  # tenta de novo
                print("Gemini falhou:", model, str(e)[:200])
    return None


def _padrao(prod):
    ganchos = {
        "cozinha": "O DETALHE QUE FALTAVA NA SUA COZINHA",
        "banheiro": "SEU BANHEIRO VAI FICAR OUTRO",
        "organizacao": "ACABOU A BAGUNÇA AQUI EM CASA",
        "limpeza": "A LIMPEZA FICOU MUITO MAIS FÁCIL",
        "decoracao": "SUA CASA MAIS LINDA GASTANDO POUCO",
    }
    return {
        "gancho": ganchos.get(prod["comodo"], "EU NÃO SABIA QUE PRECISAVA DISSO"),
        "narracao": [
            "Olha esse achadinho que eu encontrei pra sua casa!",
            f"{prod['nome']}: resolve aquele problema do dia a dia.",
            "É prático, bonito e cabe em qualquer cantinho.",
            "Se você quiser receber estes produtos com desconto para casa todos os dias, basta clicar no nome deste canal do YouTube e na bio do canal clicar no link para o WhatsApp.",
        ],
        "descricao": f"{prod['nome']} que vai facilitar sua rotina em casa. ✨",
        "tags": ["achadinhos", "achadinhos shopee", "achadinhos para casa", prod["comodo"],
                 "utilidades domesticas", "casa organizada", "achados da shopee", "produtos para casa"],
        "nome_curto": " ".join(prod["nome"].split()[:4]).upper(),
    }


def _hashtag(h):
    """Normaliza: minuscula, sem acento, so letras/numeros, com #."""
    import unicodedata
    h = unicodedata.normalize("NFKD", (h or "").lower()).encode("ascii", "ignore").decode()
    h = re.sub(r"[^a-z0-9]", "", h)
    return "#" + h if 4 <= len(h) <= 30 else None


# Mesmo metodo do canal de referencia: hashtags fixas no titulo e na descricao
HASH_TITULO = "#achadinhos #shopee #dicas"
HASH_DESCRICAO = "#achadinhos #compras #shopee #donadecasa"


def gerar(prod):
    link_produto = (prod.get("link_afiliado") or "").strip()
    prod = {k: (prod.get(k) or "") for k in ("nome", "comodo", "preco", "detalhes")}
    prod["comodo"] = normaliza_comodo(prod["comodo"])
    data = _gemini(prod) or _padrao(prod)
    comodo = prod["comodo"]

    gancho = re.sub(r"[#\n]", "", data["gancho"]).strip().upper()[:70]
    titulo = f"{gancho}   {HASH_TITULO}"[:100]
    nome_curto = re.sub(r"[#\n]", "", data.get("nome_curto") or " ".join(prod["nome"].split()[:4])).strip().upper()[:40]
    bloco_produto = f"🛍️{nome_curto}\n{link_produto}\n\n" if link_produto else f"🛍️{nome_curto}\n\n"
    descricao = (
        "🛍️ LINK DE TODOS OS PRODUTOS AQUI\n\n"
        "🔴GRUPO VIP DE PROMOÇÕES NO WHATSAPP🔴\n"
        f"{GRUPO}\n\n"
        + bloco_produto +
        "🟢GRUPO DE OFERTAS E CUPONS DE DESCONTO🟢\n"
        f"{GRUPO}\n"
        "O grupo é somente de postagem de produtos, sem chat.\n"
        "Nele você encontra achadinhos para casa com cupons de desconto todos os dias!\n\n"
        f"{HASH_DESCRICAO}"
    )
    palavra = (data.get("palavra_chave") or prod["nome"]).strip()
    tags = list(dict.fromkeys([palavra.lower()] + [t.strip().lower() for t in data.get("tags", []) if t.strip()]
                              + ["achadinhos para casa", "achadinhos", comodo]))
    # API do YouTube: tags somadas ate 500 caracteres
    out, total = [], 0
    for t in tags:
        if total + len(t) + 1 > 450:
            break
        out.append(t); total += len(t) + 1
    return {
        "gancho": gancho,
        "narracao": [s.strip() for s in data["narracao"] if s.strip()],
        "titulo": titulo,
        "descricao": descricao[:4900],
        "tags": out,
        "comodo": comodo,
        "playlist_id": PLAYLISTS.get(comodo, PLAYLISTS["organizacao"]),
    }


def normaliza_comodo(c):
    c = (c or "").lower()
    for k, alvo in [("cozinh", "cozinha"), ("banh", "banheiro"), ("organiz", "organizacao"),
                    ("limp", "limpeza"), ("decor", "decoracao"), ("quarto", "decoracao"),
                    ("sala", "decoracao")]:
        if k in c:
            return alvo
    return "organizacao"
