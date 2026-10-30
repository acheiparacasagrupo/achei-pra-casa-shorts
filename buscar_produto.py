"""
buscar_produto.py
Busca produtos virais no Mercado Livre e insere na planilha como pendente.
"""
import json, os, random, re, sys
import requests
import gspread
from google.oauth2.service_account import Credentials

GEMINI_API_KEY          = os.environ["GEMINI_API_KEY"]
GOOGLE_CREDENTIALS_JSON = os.environ["GOOGLE_CREDENTIALS"]
PLANILHA_ID             = os.environ.get("PLANILHA_ID", "1DEXtunlKTCBKu3lmYYPLp8X0nsuSNaRe8CaSLdExLbU")

COMODOS = ["cozinha", "banheiro", "limpeza", "decoracao", "organizacao"]

QUERIES_FALLBACK = {
    "cozinha":     ["organizador gaveta cozinha", "suporte temperos geladeira", "escorredor talheres"],
    "banheiro":    ["organizador banheiro suspenso", "porta shampoo banheiro", "suporte papel higienico"],
    "limpeza":     ["rodo magico giratorio", "mop spray limpeza", "kit limpeza multiuso"],
    "decoracao":   ["quadro decorativo sala", "vaso ceramica decorativo", "luminaria led mesa"],
    "organizacao": ["caixa organizadora multiuso", "organizador gaveta roupas", "organizador bolsa"],
}

DESCRICAO_FALLBACK = {
    "cozinha":     "Produto pratico para organizar sua cozinha e resolver o problema de espaco.",
    "banheiro":    "Solucao inteligente para o banheiro. Maximiza espaco sem perfurar paredes.",
    "limpeza":     "Facilita a limpeza do dia a dia. Economiza tempo com resultado muito melhor.",
    "decoracao":   "Transforma o ambiente com estilo moderno que combina com qualquer casa.",
    "organizacao": "Organiza de uma vez por todas. Chega de perder tempo procurando as coisas.",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ProdutoBot/1.0)",
    "Accept": "application/json",
}


def _gemini(prompt):
    """Chama Gemini com timeout curto para falhar rapido."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    r = requests.post(url, params={"key": GEMINI_API_KEY},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"maxOutputTokens": 300}},
        timeout=10)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def gerar_queries(comodo):
    """Pede ao Gemini 3 queries. Usa fallback imediato se falhar."""
    try:
        r = _gemini("Gere 3 queries de busca em portugues (max 4 palavras) para produtos virais de " + comodo + " no Mercado Livre. Retorne APENAS as 3 queries, uma por linha.")
        queries = [q.strip() for q in r.strip().splitlines() if q.strip()][:3]
        if queries:
            print("  Queries Gemini: " + str(queries))
            return queries
    except Exception as e:
        print("  Gemini falhou, usando fallback: " + str(e))
    fallback = QUERIES_FALLBACK.get(comodo, ["produto viral casa", "gadget utilidade domestica", "achadinho tiktok"])
    print("  Queries fallback: " + str(fallback))
    return fallback


def gerar_detalhes(nome, preco, comodo):
    """Gemini gera descricao. Usa fallback imediato se falhar."""
    try:
        r = _gemini("Produto: " + nome + " R$" + str(round(preco,2)) + " comodo: " + comodo + ". Descricao curta (max 180 chars) sem emojis.")
        if r.strip():
            return r[:200]
    except Exception as e:
        print("  Gemini falhou para detalhes: " + str(e))
    return DESCRICAO_FALLBACK.get(comodo, "Produto pratico para " + comodo + ".")[:200]


def buscar_ml(query, comodo):
    """Busca na API publica do ML sem autenticacao."""
    try:
        # Sem sort=sold_quantity_desc pois requer auth - usamos sort por relevancia
        resp = requests.get("https://api.mercadolibre.com/sites/MLB/search",
            params={"q": query, "limit": 20, "condition": "new"},
            headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resultados = resp.json().get("results", [])
    except Exception as e:
        print("  ML API erro: " + str(e))
        return None

    # Filtra por preco e quantidade de vendas
    filtrados = [p for p in resultados if 15 <= p.get("price", 0) <= 120
        and p.get("thumbnail", "").startswith("http") and p.get("sold_quantity", 0) >= 50]
    if not filtrados:
        filtrados = [p for p in resultados if 15 <= p.get("price", 0) <= 120
            and p.get("thumbnail", "").startswith("http")]
    if not filtrados:
        return None

    # Ordena pelos mais vendidos
    filtrados.sort(key=lambda p: p.get("sold_quantity", 0), reverse=True)
    melhor = filtrados[0]

    try:
        det = requests.get("https://api.mercadolibre.com/items/" + melhor["id"],
            headers=HEADERS, timeout=10).json()
        imagem = det.get("pictures", [{}])[0].get("url", melhor["thumbnail"])
        imagem = re.sub(r"-[A-Z]\.jpg$", "-O.jpg", imagem)
    except Exception:
        imagem = re.sub(r"-[A-Z]\.jpg$", "-O.jpg", melhor.get("thumbnail", ""))

    print("  Encontrado: " + melhor["title"][:60] + " | R$" + str(melhor["price"]) + " | " + str(melhor.get("sold_quantity", 0)) + " vendas")
    return {"nome": melhor["title"][:80], "comodo": comodo, "preco": melhor["price"],
            "link_afiliado": melhor["permalink"], "imagens": imagem}


def inserir_planilha(produto):
    """Insere o produto como nova linha pendente na planilha."""
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_CREDENTIALS_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    ws = gspread.authorize(creds).open_by_key(PLANILHA_ID).sheet1
    ws.append_row([
        "pendente", produto["nome"], produto["comodo"], produto["preco"],
        produto["link_afiliado"], produto["imagens"], produto.get("detalhes", ""),
        "", "", "", "",
    ], value_input_option="USER_ENTERED")
    print("Produto inserido: " + produto["nome"] + " R$" + str(produto["preco"]))


def main():
    comodo = random.choice(COMODOS)
    print("Buscando produto viral para: " + comodo)
    produto = None
    comodos_tentados = [comodo]
    for _ in range(5):
        queries = gerar_queries(comodo)
        for query in queries:
            print("  Buscando ML: " + query)
            p = buscar_ml(query, comodo)
            if p:
                produto = p
                break
        if produto:
            break
        restantes = [c for c in COMODOS if c not in comodos_tentados]
        if not restantes:
            break
        comodo = random.choice(restantes)
        comodos_tentados.append(comodo)
        print("  Tentando comodo: " + comodo)
    if not produto:
        sys.exit("ERRO: Nao foi possivel encontrar produto no ML.")
    produto["detalhes"] = gerar_detalhes(produto["nome"], produto["preco"], comodo)
    inserir_planilha(produto)


if __name__ == "__main__":
    main()
