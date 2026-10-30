"""
buscar_produto.py
Usa Gemini para gerar queries de busca e chama a API publica do Mercado Livre
para encontrar produtos virais para casa. Insere na planilha como 'pendente'.

Variaveis de ambiente necessarias:
  GEMINI_API_KEY       - chave da API Gemini
  GOOGLE_CREDENTIALS   - JSON de service account com acesso a planilha (editor)
  PLANILHA_ID          - ID da planilha (opcional, usa padrao se omitido)
"""
import json, os, random, re, sys
import requests
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

GEMINI_API_KEY       = os.environ["GEMINI_API_KEY"]
GOOGLE_CREDENTIALS_JSON = os.environ["GOOGLE_CREDENTIALS"]
PLANILHA_ID          = os.environ.get("PLANILHA_ID", "1DEXtunlKTCBKu3lmYYPLp8X0nsuSNaRe8CaSLdExLbU")

COMODOS = ["cozinha", "banheiro", "limpeza", "decoracao", "organizacao"]

# ââ Gemini ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def _gemini(prompt: str) -> str:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    return model.generate_content(prompt).text.strip()


def gerar_queries(comodo: str) -> list:
    """Pede ao Gemini 3 queries de busca para produtos virais no comodo dado."""
    r = _gemini(f"""Voce e especialista em produtos virais para casa no Brasil.

Gere 3 queries de busca diferentes (em portugues, max 5 palavras cada) para encontrar
no Mercado Livre produtos VIRAIS para o comodo: {comodo}

Criterios:
- Resolvem uma dor real do dia a dia
- Sao gadgets/achadinhos que viralizam no TikTok e Reels
- Preco acessivel entre R$15 e R$120
- Muito vendidos no Brasil
- Nao repita produtos ja comuns (prefer produtos inovadores/surpresa)

Retorne APENAS as 3 queries, uma por linha, sem numeracao, sem explicacao.
Exemplo:
organizador talheres bambu
suporte temperos geladeira
dispenser sabonete automatico""")

    return [q.strip() for q in r.strip().splitlines() if q.strip()][:3]


def gerar_detalhes(nome: str, preco: float, comodo: str) -> str:
    """Gemini gera descricao atrativa do produto (max 180 chars)."""
    r = _gemini(f"""Produto do Mercado Livre:
Nome: {nome}
Preco: R${preco:.2f}
Comodo: {comodo}

Escreva uma descricao curta (MAX 180 caracteres) em portugues que destaque:
- A dor que resolve no dia a dia
- O principal diferencial
- Linguagem natural, sem exageros

Retorne APENAS a descricao, sem aspas, sem emojis.""")
    return r[:200]


# ââ Mercado Livre API publica âââââââââââââââââââââââââââââââââââââââââââââââââ

def buscar_ml(query: str, comodo: str) -> dict:
    """Busca na API publica do ML e retorna o melhor produto encontrado."""
    try:
        params = {
            "q": query,
            "sort": "sold_quantity_desc",
            "limit": 20,
            "condition": "new",
        }
        resp = requests.get(
            "https://api.mercadolibre.com/sites/MLB/search",
            params=params, timeout=15
        )
        resp.raise_for_status()
        resultados = resp.json().get("results", [])
    except Exception as e:
        print(f"  ML API erro: {e}")
        return None

    # filtra por preco e thumbnail valido
    filtrados = [
        p for p in resultados
        if 15 <= p.get("price", 0) <= 120
        and p.get("thumbnail", "").startswith("http")
        and p.get("sold_quantity", 0) >= 50
    ]
    # fallback sem filtro de vendas minimas
    if not filtrados:
        filtrados = [
            p for p in resultados
            if 15 <= p.get("price", 0) <= 120
            and p.get("thumbnail", "").startswith("http")
        ]
    if not filtrados:
        return None

    melhor = filtrados[0]
    produto_id = melhor["id"]

    # busca imagem em maior resolucao
    try:
        det = requests.get(
            f"https://api.mercadolibre.com/items/{produto_id}",
            timeout=10
        ).json()
        imagem = det.get("pictures", [{}])[0].get("url", melhor["thumbnail"])
        # mlstatic: sufixo -O.jpg = full size, -I.jpg = pequena
        imagem = re.sub(r"-[A-Z]\.jpg$", "-O.jpg", imagem)
    except Exception:
        imagem = re.sub(r"-[A-Z]\.jpg$", "-O.jpg", melhor.get("thumbnail", ""))

    print(f"  Encontrado: {melhor['title'][:60]} | R${melhor['price']:.2f} | {melhor.get('sold_quantity',0)} vendas")

    return {
        "nome": melhor["title"][:80],
        "comodo": comodo,
        "preco": melhor["price"],
        "link_afiliado": melhor["permalink"],
        "imagens": imagem,
    }


# ââ Planilha ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def inserir_planilha(produto: dict):
    """Insere o produto como nova linha 'pendente' na planilha."""
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(PLANILHA_ID).sheet1

    nova_linha = [
        "pendente",
        produto["nome"],
        produto["comodo"],
        produto["preco"],
        produto["link_afiliado"],
        produto["imagens"],
        produto.get("detalhes", ""),
        "",  # titulo  (preenchido pelo run.py via Gemini)
        "",  # video_id
        "",  # data_postagem
        "",  # videos
    ]
    ws.append_row(nova_linha, value_input_option="USER_ENTERED")
    print(f"Produto inserido na planilha: {produto['nome']} ({produto['comodo']}) R${produto['preco']:.2f}")


# ââ Main ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def main():
    comodo = random.choice(COMODOS)
    print(f"Buscando produto viral para: {comodo}")

    produto = None
    comodos_tentados = [comodo]

    for _ in range(5):
        queries = gerar_queries(comodo)
        print(f"  Queries Gemini: {queries}")

        for query in queries:
            print(f"  Buscando ML: '{query}'")
            p = buscar_ml(query, comodo)
            if p:
                produto = p
                break
        if produto:
            break

        # tenta outro comodo se nao achou
        restantes = [c for c in COMODOS if c not in comodos_tentados]
        if not restantes:
            break
        comodo = random.choice(restantes)
        comodos_tentados.append(comodo)
        print(f"  Sem resultado. Tentando comodo: {comodo}")

    if not produto:
        sys.exit("ERRO: Nao foi possivel encontrar produto no ML apos varias tentativas.")

    produto["detalhes"] = gerar_detalhes(produto["nome"], produto["preco"], comodo)
    inserir_planilha(produto)


if __name__ == "__main__":
    main()
