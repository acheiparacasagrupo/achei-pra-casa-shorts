"""Gera titulo, narracao, descricao e tags do Short com o Gemini (plano gratuito).
Se nao houver chave ou a API falhar, usa um modelo de texto pronto."""
import json, os, random, re, requests

GRUPO = os.environ.get("LINK_GRUPO", "https://chat.whatsapp.com/Dm1Mv7qgbPRDNZN1zvLZRz")
HASH_TITULO = "#achadinhos #shopee #dicas"
HASH_BASE = ["#achadinhos", "#shopee", "#dicas", "#achadinhosdacasa", "#casaorganizada",
             "#utilidadesdomesticas", "#donadecasa", "#shopeebrasil", "#achadosdashopee"]
HASH_COMODO = {
    "cozinha": ["#cozinha", "#cozinhaorganizada", "#utensiliosdecozinha"],
    "banheiro": ["#banheiro", "#banheirodecorado", "#banheiroorganizado"],
    "organizacao": ["#organizacao", "#casaorganizada", "#organizadores"],
    "limpeza": ["#limpeza", "#dicasdelimpeza", "#limpezadacasa"],
    "decoracao": ["#decoracao", "#decoracaobarata", "#casaaconchegante"],
}

PROMPT = """Voce e roteirista de um canal brasileiro de YouTube Shorts chamado "Achei pra Casa", que mostra achadinhos baratos para casa (Shopee/Mercado Livre) e leva o publico para um grupo VIP de ofertas no WhatsApp.

Produto: {nome}
Comodo: {comodo}
Preco (pode estar vazio): {preco}
Detalhes (pode estar vazio): {detalhes}

Crie o texto de UM Short de 20 a 28 segundos. Regras:
- "gancho": titulo em CAIXA ALTA, no maximo 55 caracteres, focado no BENEFICIO, na DOR resolvida ou na CURIOSIDADE, SEM dizer o nome do produto. Use formulas que viralizam no nicho, por exemplo: "O DETALHE QUE FALTAVA NA SUA COZINHA", "PARE DE SOFRER PRA LIMPAR O BOX", "EU NAO SABIA QUE PRECISAVA DISSO", "ISSO CUSTA MENOS QUE UM LANCHE", "QUEM TEM CASA PEQUENA PRECISA VER ISSO". Nao use emoji nem hashtag no gancho. Use acentuacao correta em portugues.
- "narracao": lista de 4 a 6 frases curtas, faladas, tom animado e natural de amiga indicando um achado, total entre 55 e 75 palavras. Frase 1 = gancho forte que prende nos 2 primeiros segundos. Frases do meio = o problema que resolve e 2 beneficios concretos. Ultima frase = CTA exatamente com a ideia: "O link com desconto ta no nosso grupo VIP, e so tocar em link clique aqui." Nao invente preco nem medidas que nao foram informadas. Sem emojis.
- "descricao": 2 frases vendedoras sobre o produto (pode ter 1 ou 2 emojis).
- "tags": 12 palavras-chave de busca em portugues, minusculas, sem #, mistas entre o produto, o comodo e "achadinhos shopee".
- "hashtags": 3 hashtags extras especificas do produto, minusculas, sem acento, comecando com #.

Responda SOMENTE com JSON: {{"gancho": "...", "narracao": ["..."], "descricao": "...", "tags": ["..."], "hashtags": ["#..."]}}"""


def _gemini(prod):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(**prod)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
    }
    for _ in range(3):
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key}, json=body, timeout=60)
            r.raise_for_status()
            txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(txt)
            if data.get("gancho") and data.get("narracao"):
                return data
        except Exception as e:  # tenta de novo
            print("Gemini falhou:", e)
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
            f"É {prod['nome'].lower()}, e resolve aquele problema do dia a dia.",
            "É prático, bonito e cabe em qualquer cantinho.",
            "O link com desconto tá no nosso grupo VIP, é só tocar em link clique aqui.",
        ],
        "descricao": f"{prod['nome']} que vai facilitar sua rotina em casa. ✨",
        "tags": ["achadinhos", "achadinhos shopee", "achadinhos para casa", prod["comodo"],
                 "utilidades domesticas", "casa organizada", "achados da shopee", "produtos para casa"],
        "hashtags": [],
    }


def gerar(prod):
    prod = {k: (prod.get(k) or "") for k in ("nome", "comodo", "preco", "detalhes")}
    prod["comodo"] = normaliza_comodo(prod["comodo"])
    data = _gemini(prod) or _padrao(prod)

    gancho = re.sub(r"[#\n]", "", data["gancho"]).strip().upper()[:70]
    titulo = f"{gancho} {HASH_TITULO}"[:100]
    extras = [h if h.startswith("#") else "#" + h for h in data.get("hashtags", [])][:3]
    hashtags = list(dict.fromkeys(HASH_BASE + HASH_COMODO.get(prod["comodo"], []) + extras))
    descricao = (
        f"🛍️ LINK DESTE PRODUTO COM DESCONTO AQUI 👇\n"
        f"Entre no nosso grupo VIP de achadinhos para casa no WhatsApp:\n{GRUPO}\n\n"
        f"{data.get('descricao', '').strip()}\n\n"
        f"Inscreva-se no canal pra ver novos achadinhos todo dia! 🏠💖\n\n"
        + " ".join(hashtags)
    )
    tags = list(dict.fromkeys([t.strip().lower() for t in data.get("tags", []) if t.strip()]
                              + ["achadinhos", "achadinhos shopee", "achadinhos para casa"]))
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
        "comodo": prod["comodo"],
    }


def normaliza_comodo(c):
    c = (c or "").lower()
    for k, alvo in [("cozinh", "cozinha"), ("banh", "banheiro"), ("organiz", "organizacao"),
                    ("limp", "limpeza"), ("decor", "decoracao"), ("quarto", "decoracao"),
                    ("sala", "decoracao")]:
        if k in c:
            return alvo
    return "organizacao"
