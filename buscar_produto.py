"""
buscar_produto.py v3 — sem dependencia da API do Mercado Livre
- Usa google-genai SDK (gemini-2.0-flash) para gerar dados do produto
- Usa loremflickr para imagens reais (sem API key necessaria)
- Gera URL de busca do Mercado Livre como link do produto
"""
import json, os, random, re, sys, requests
from google import genai
import gspread
from google.oauth2.service_account import Credentials

GEMINI_API_KEY       = os.environ["GEMINI_API_KEY"]
GOOGLE_CREDENTIALS_JSON = os.environ["GOOGLE_CREDENTIALS"]
PLANILHA_ID          = os.environ.get("PLANILHA_ID", "1DEXtunlKTCBKu3lmYYPLp8X0nsuSNaRe8CaSLdExLbU")

COMODOS = ["cozinha", "banheiro", "limpeza", "decoracao", "organizacao"]

FALLBACK_PRODUTOS = {
    "cozinha": {
        "nome": "Organizador de Talheres Bambu 3 Divisoes",
        "preco": 39.90,
        "detalhes": "Organiza talheres de vez. Bambu resistente, encaixa em qualquer gaveta. Chega de baguncia.",
        "query": "organizador talheres bambu cozinha",
    },
    "banheiro": {
        "nome": "Suporte Shampoo Inox Adesivo Sem Furo",
        "preco": 28.90,
        "detalhes": "Fixa sem furar a parede. Inox resistente, aguenta shampoo, condicionador e sabonete.",
        "query": "suporte shampoo inox sem furo banheiro",
    },
    "limpeza": {
        "nome": "Rodo Magico Giratorio Mop 360 Graus",
        "preco": 59.90,
        "detalhes": "Limpa o chao sem dobrar as costas. Gira 360 graus e escorre sozinho. Sensacao de casa limpa.",
        "query": "rodo magico giratorio mop limpeza",
    },
    "decoracao": {
        "nome": "Luminaria LED Touch Recarregavel USB",
        "preco": 45.90,
        "detalhes": "Ilumina qualquer ambiente sem fio. Tres tons de luz, toque para ligar. Perfeita para cabeceira.",
        "query": "luminaria led touch recarregavel usb",
    },
    "organizacao": {
        "nome": "Caixa Organizadora Dobravel com Tampa",
        "preco": 34.90,
        "detalhes": "Dobra quando nao usa, abre quando precisa. Ideal para roupas, brinquedos ou objetos.",
        "query": "caixa organizadora dobravel com tampa",
    },
}


def _gemini(prompt: str) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return resp.text.strip()


def gerar_produto(comodo: str) -> dict:
    """Gera dados do produto usando Gemini, com fallback hardcoded."""
    try:
        r = _gemini(
            "Voce e especialista em produtos virais para casa no Brasil.\n\n"
            f"Gere 1 produto viral para o comodo: {comodo}\n\n"
            "Criterios:\n"
            "- Preco entre R$15 e R$120\n"
            "- Gadget/achadinho que viraliza no TikTok e Reels\n"
            "- Produto real, muito vendido no Brasil\n"
            "- Resolve uma dor real do dia a dia\n\n"
            "Retorne APENAS JSON valido (sem markdown, sem explicacoes):\n"
            '{"nome": "nome do produto (max 80 chars)", "preco": 49.90, '
            '"detalhes": "descricao atrativa max 180 chars sem emojis", '
            '"query": "3-5 palavras de busca em portugues"}'
        )
        # Limpar markdown se presente
        r = re.sub(r"```\w*\s*", "", r).strip()
        if r.startswith("```"):
            r = r[3:]
        if r.endswith("```"):
            r = r[:-3]
        dados = json.loads(r.strip())
        print(f"  Gemini gerou: {str(dados.get('nome', ''))[:60]}")
        return dados
    except Exception as e:
        print(f"  Gemini falhou ({e}), usando fallback")
        return dict(FALLBACK_PRODUTOS.get(comodo, FALLBACK_PRODUTOS["cozinha"]))


def buscar_imagem(query: str) -> str:
    """Busca imagem real via loremflickr (sem API key, imagens reais do Flickr)."""
    try:
        keyword = query.replace(" ", ",")[:80]
        resp = requests.get(
            f"https://loremflickr.com/800/800/{keyword}",
            timeout=15,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200 and resp.url.startswith("https://"):
            print(f"  Imagem: {resp.url[:80]}")
            return resp.url
    except Exception as e:
        print(f"  loremflickr falhou: {e}")

    # Fallback: imagem placeholder colorida valida
    kw = query[:30].replace(" ", "+")
    return f"https://placehold.co/800x800/FF6B35/FFFFFF/png?text={kw}"


def inserir_planilha(produto: dict):
    """Insere o produto como nova linha 'pendente' na planilha."""
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_CREDENTIALS_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    ws = gspread.authorize(creds).open_by_key(PLANILHA_ID).sheet1
    link = "https://www.mercadolivre.com.br/busca?q=" + produto["query"].replace(" ", "+")
    ws.append_row(
        [
            "pendente",
            produto["nome"],
            produto.get("comodo", "casa"),
            produto["preco"],
            link,
            produto.get("imagens", ""),
            produto.get("detalhes", ""),
            "",  # titulo  (preenchido pelo run.py via Gemini)
            "",  # video_id
            "",  # data_postagem
            "",  # videos
        ],
        value_input_option="USER_ENTERED",
    )
    print(f"Produto inserido: {produto['nome']} R${float(produto['preco']):.2f}")


def main():
    comodo = random.choice(COMODOS)
    print(f"Gerando produto viral para: {comodo}")

    produto = gerar_produto(comodo)
    produto["comodo"] = comodo
    produto["imagens"] = buscar_imagem(produto.get("query", produto["nome"]))
    inserir_planilha(produto)


if __name__ == "__main__":
    main()
