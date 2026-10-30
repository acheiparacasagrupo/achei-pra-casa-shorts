"""
buscar_produto.py
Usa Gemini para gerar queries de busca e chama a API publica do Mercado Livre
para encontrar produtos virais para casa. Insere na planilha como pendente.

Variaveis de ambiente necessarias:
  GEMINI_API_KEY       - chave da API Gemini
  GOOGLE_CREDENTIALS   - JSON de service account com acesso a planilha (editor)
  PLANILHA_ID          - ID da planilha (opcional, usa padrao se omitido)
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
    "cozinha":     ["organizador gaveta cozinha bambu", "suporte temperos geladeira", "escorredor talheres vertical"],
    "banheiro":    ["organizador banheiro suspenso", "porta shampoo adesivo banheiro", "suporte papel higienico"],
    "limpeza":     ["rodo magico giratorio cabo", "mop spray limpeza rapida", "kit limpeza multiuso casa"],
    "decoracao":   ["quadro decorativo minimalista sala", "vaso ceramica decorativo moderno", "luminaria led mesa"],
    "organizacao": ["caixa organizadora multiuso", "organizador gaveta roupas", "divisor compartimento bolsa"],
}

DESCRICAO_FALLBACK = {
    "cozinha":     "Produto pratico para organizar sua cozinha. Resolve o problema de espaco e deixa tudo no lugar certo.",
    "banheiro":    "Solucao inteligente para banheiro. Maximiza o espaco e mantem tudo organizado sem perfurar paredes.",
    "limpeza":     "Facilita a limpeza do dia a dia. Economiza tempo e esfoco com um resultado muito melhor.",
    "decoracao":   "Transforma o ambiente com estilo. Decoracao moderna que combina com qualquer estilo de casa.",
    "organizacao": "Organiza de uma vez por todas. Chega de perder tempo procurando as coisas em casa.",
}

# -- Gemini (timeout curto: falha rapido e usa fallback) ---------------------

def _gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    r = requests.post(url, params={"key": GEMINI_API_KEY},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"maxOutputTokens": 300}},
        timeout=10)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def gerar_queries(comodo):
    try:
        r = _gemini("Gere 3 queries de busca (portugues, max 5 palavras) para produtos virais de " + comodo + " no Mercado Livre. Retorne APENAS as 3 queries, uma por linha.")
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
    try:
        r = _gemini("Produto: " + nome + " R$" + str(round(preco,2)) + " comodo: " + comodo + ". Descricao curta (max 180 chars) em portugues, sem emojis.")
        if r.strip():
            return r[:200]
    except Exception as e:
        print("  Gemini falhou para detalhes, usando fallback: " + str(e))
    desc = DESCRICAO_FALLBACK.get(comodo, "Produto pratico para " + comodo + ". Resolve problemas do dia a dia.")
    return desc[:200]


# -- Mercado Livre API -------------------------------------------------------

def buscar_ml(query, comodo):
    try:
        resp = requests.get("https://api.mercadolibre.com/sites/MLB/search",
            params={"q": query, "sort": "sold_quantity_desc", "limit": 20, "condition": "new"},
            timeout=15)
        resp.raise_for_status()
        resultados = resp.json().get("results", [])
    except Exception as e:
        print("  ML API erro: " + str(e))
        return None

    filtrados = [p for p in resultados
        if 15 <= p.get("price", 0) <= 120
        and p.get("thumbnail", "").startswith("http")
        and p.get("sold_quantity", 0) >= 50]
    if not filtrados:
        filtrados = [p for p in resultados
            if 15 <= p.get("price", 0) <= 120
            and p.get("thumbnail", "").startswith("http")]
    if not filtrados:
        return None

    melhor = filtrados[0]
    try:
        det = requests.get("https://api.mercadolibre.com/items/" + melhor["id"], timeout=10).json()
        imagem = det.get("pictures", [{}])[0].get("url", melhor["thumbnail"])
        imagem = re.sub(r"-[A-Z]\.jpg$", "-O.jpg", imagem)
    except Exception:
        imagem = re.sub(r"-[A-Z]\.jpg$", "-O.jpg", melhor.get("thumbnail", ""))

    print("  Encontrado: " + melhor["title"][:60] + " | R$" + str(melhor["price"]) + " | " + str(melhor.get("sold_quantity",0)) + " vendas")
    return {
        "nome": melhor["title"][:80],
        "comodo": comodo,
        "preco": melhor["price"],
        "link_afiliado": melhor["permalink"],
        "imagens": imagem,
    }


# -- Planilha ----------------------------------------------------------------

def inserir_planilha(produto):
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


# -- Main --------------------------------------------------------------------

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
