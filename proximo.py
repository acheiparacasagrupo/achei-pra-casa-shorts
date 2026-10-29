"""Le a planilha (link publico, so leitura) e escolhe o proximo produto com status 'pendente'.
Grava payload.json. Se nao houver produto, grava pular=1 para o workflow encerrar sem erro."""
import csv, io, json, os, sys, requests

PLANILHA = os.environ.get("PLANILHA_ID") or "1DEXtunlKTCBKu3lmYYPLp8X0nsuSNaRe8CaSLdExLbU"
ABA = os.environ.get("PLANILHA_ABA") or "Produtos"
url = f"https://docs.google.com/spreadsheets/d/{PLANILHA}/gviz/tq?tqx=out:csv&headers=1&sheet={ABA}"

r = requests.get(url, timeout=30)
r.raise_for_status()
if r.text.lstrip().startswith("<"):
    sys.exit("A planilha nao esta publica. Compartilhe como 'Qualquer pessoa com o link: Leitor'.")

linhas = list(csv.DictReader(io.StringIO(r.text)))
saida = os.environ.get("GITHUB_OUTPUT", "/dev/null")
candidatos = []
for i, l in enumerate(linhas):
    l = {k.strip().lower(): (v or "").strip() for k, v in l.items() if k}
    if l.get("nome") and (l.get("imagens") or l.get("videos")) and l.get("status", "").lower() in ("pendente", ""):
        candidatos.append((0 if l.get("videos") else 1, i, l))  # produtos com video real primeiro
if candidatos:
    _, i, l = sorted(candidatos, key=lambda c: (c[0], c[1]))[0]
    payload = {"row_id": str(i + 2), **{k: l.get(k, "") for k in ("nome", "comodo", "preco", "detalhes", "imagens", "videos", "link_afiliado")}}
    json.dump(payload, open("payload.json", "w"), ensure_ascii=False)
    print("Produto escolhido (linha", i + 2, "):", payload["nome"], "| video real:", bool(l.get("videos")))
    open(saida, "a").write("pular=0\n")
else:
    print("Nenhum produto pendente na planilha.")
    open(saida, "a").write("pular=1\n")
