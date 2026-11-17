# =============================================================================
# Interface Streamlit — Agente Curador de Notícias (N0, N1, N2 e N3)
# =============================================================================
# COMO USAR
#   1. Coloque ESTE arquivo na mesma pasta dos seus scripts
#      (N0_agent_curador.py, N1_agent_curador.py, N2.py, N3_agent_curador.py)
#   2. Instale:   pip install streamlit
#   3. Rode:      streamlit run app_curador.py
#
# O app NÃO altera seus scripts: ele apenas importa o agente/workflow de cada
# um e chama o método .run() com o tema digitado na tela.
# =============================================================================

import importlib
import os
import sys
import time
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))  # permite importar os scripts da mesma pasta
load_dotenv(BASE_DIR / ".env")


def segredo(nome, padrao=None):
    """Lê um valor de .streamlit/secrets.toml (local) ou de Settings > Secrets (nuvem)."""
    try:
        return st.secrets[nome]
    except Exception:
        return padrao


# Os seus scripts leem a chave com os.getenv(). Na nuvem não existe arquivo .env,
# então copiamos a chave dos Secrets para o ambiente ANTES de importar os scripts.
if segredo("OPENAI_API_KEY"):
    os.environ.setdefault("OPENAI_API_KEY", str(segredo("OPENAI_API_KEY")))

# -----------------------------------------------------------------------------
# 1. CATÁLOGO DAS VERSÕES
#    Para cada versão: qual arquivo importar, qual objeto usar e onde ela salva.
#    (N0 salva em "output/NO" com letra O e N3 salva em "output/N1": isso é
#    exatamente o que está nos seus scripts, por isso mantive igual aqui.)
# -----------------------------------------------------------------------------
VERSOES = {
    "N0": {
        "titulo": "N0 — Agente único (skills no prompt)",
        "modulo": "N0_agent_curador",
        "objeto": "agente_noticias",
        "saida": "output/NO",
        "usa_skills_dir": False,
        "etapas": ["Agente único (pesquisa → apuração → verificação → redação)"],
        "descricao": "Um único agente faz tudo. As 4 skills estão escritas "
                     "dentro do próprio código, no prompt.",
        "exemplo": "Trump questiona eleição brasileira e Alckmin rebate: “equivocado”",
    },
    "N1": {
        "titulo": "N1 — Agente único (skills em arquivos)",
        "modulo": "N1_agent_curador",
        "objeto": "agente_noticias",
        "saida": "output/N1",
        "usa_skills_dir": True,
        "etapas": ["Agente único carregando skills da pasta /skills"],
        "descricao": "Mesmo agente do N0, mas as skills ficam em arquivos "
                     "na pasta 'skills' (código mais limpo).",
        "exemplo": "Trump questiona eleição brasileira e Alckmin rebate: “equivocado”",
    },
    "N2": {
        "titulo": "N2 — Workflow com 4 agentes",
        "modulo": "N2",
        "objeto": "workflow",
        "saida": "output/N2",
        "usa_skills_dir": True,
        "etapas": ["Pesquisador", "Apurador de Fontes", "Verificador Factual", "Redator"],
        "descricao": "Equipe de 4 agentes especialistas em sequência; "
                     "a saída de um alimenta o próximo.",
        "exemplo": "Novas tarifas dos EUA entram em vigor com taxa de 10%",
    },
    "N3": {
        "titulo": "N3 — Workflow com Team e Loop",
        "modulo": "N3_agent_curador",
        "objeto": "news_curator_workflow",
        "saida": "output/N1",
        "usa_skills_dir": True,
        "etapas": ["Pesquisa (Team)", "Apuração", "Verificação factual", "Redação"],
        "descricao": "Workflow com equipe (Team) na pesquisa e regra de mínimo "
                     "de fontes na apuração.",
        "exemplo": "Novas tarifas dos EUA entram em vigor com taxa de 10%",
    },
}


# -----------------------------------------------------------------------------
# 2. FUNÇÕES AUXILIARES
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Carregando o agente...")
def carregar_objeto(modulo: str, objeto: str):
    """Importa o script escolhido e devolve o agente/workflow já montado."""
    mod = importlib.import_module(modulo)
    return getattr(mod, objeto)


def listar_md(pasta: Path) -> dict:
    """Devolve {arquivo: data_de_modificação} de todos os .md da pasta."""
    if not pasta.exists():
        return {}
    return {p: p.stat().st_mtime for p in pasta.rglob("*.md")}


def arquivos_novos(antes: dict, depois: dict) -> list:
    """Arquivos criados ou alterados durante a execução, do mais novo ao mais antigo."""
    novos = [p for p, t in depois.items() if p not in antes or t > antes[p]]
    return sorted(novos, key=lambda p: depois[p], reverse=True)


def extrair_texto(resposta) -> str:
    """Pega o texto final da resposta (agente ou workflow)."""
    conteudo = getattr(resposta, "content", None)
    if conteudo is None:
        return ""
    return conteudo if isinstance(conteudo, str) else str(conteudo)



# -----------------------------------------------------------------------------
# 2B. PLANOS MENSAIS (um por versão/agente)
#     ATENÇÃO: preços e limites abaixo são EXEMPLOS. Ajuste depois de medir quanto
#     cada matéria custa na sua conta da OpenAI (painel de Usage).
#     O link de pagamento de cada plano vem dos Secrets: [checkout] N0 = "https://..."
# -----------------------------------------------------------------------------
PLANOS = {
    "N0": {
        "nome": "Básico", "preco": "R$ 49,90", "limite": "10 matérias/mês",
        "itens": ["Agente único (rápido e simples)", "Pesquisa, apuração, verificação e redação",
                  "Matéria em Markdown para baixar"],
    },
    "N1": {
        "nome": "Padrão", "preco": "R$ 59,90", "limite": "20 matérias/mês",
        "itens": ["Agente único com skills em arquivos", "Mesmo fluxo completo do Básico",
                  "Instruções mais fáceis de evoluir"],
    },
    "N2": {
        "nome": "Pro", "preco": "R$ 79,90", "limite": "30 matérias/mês",
        "itens": ["Equipe de 4 agentes especialistas", "Citações [1], [2] e seção de Referências",
                  "Cada etapa salva em arquivo"],
    },
    "N3": {
        "nome": "Premium", "preco": "R$ 119,90", "limite": "50 matérias/mês",
        "itens": ["Equipe (Team) na pesquisa", "Regra de mínimo de fontes",
                  "Aviso automático quando há poucas fontes", "Prioridade nas novidades"],
    },
}


def mostrar_planos():
    st.title("💳 Planos mensais")
    st.caption("Cada plano libera um agente diferente. Pagamento seguro pelo checkout do plano.")
    links = segredo("checkout", {}) or {}
    colunas = st.columns(len(PLANOS))
    for col, (chave_v, plano) in zip(colunas, PLANOS.items()):
        with col, st.container(border=True):
            st.markdown(f"#### {plano['nome']}")
            st.caption(VERSOES[chave_v]["titulo"])
            st.markdown(f"## {plano['preco']}")
            st.markdown("por mês")
            st.markdown(f"**{plano['limite']}**")
            for item in plano["itens"]:
                st.markdown(f"✓ {item}")
            url = str(links.get(chave_v, "")) if hasattr(links, "get") else ""
            if url.startswith("http"):
                st.link_button("Assinar agora", url, type="primary", use_container_width=True)
            else:
                st.button("Assinar agora", key=f"assinar_{chave_v}", disabled=True,
                          use_container_width=True, help="Link de pagamento ainda não configurado.")
    st.info("Depois do pagamento aprovado, você recebe um **código de acesso**. "
            "Digite-o na barra lateral, em 'Gerar matéria'.")


# -----------------------------------------------------------------------------
# 2C. CONTROLE DE ACESSO E DE USO (Supabase)
#     A "catraca": confere código, versão liberada, validade e limites ANTES de
#     chamar a OpenAI. A contagem fica no Supabase (não some quando o app reinicia).
# -----------------------------------------------------------------------------
MENSAGENS = {
    "codigo_invalido": "Código inválido.",
    "inativo": "Este código foi desativado.",
    "expirado": "Este código expirou. Renove sua assinatura.",
    "versao_nao_liberada": "Seu plano não inclui esta versão do agente.",
    "aguarde": "Aguarde alguns segundos antes de gerar outra matéria.",
    "limite_diario": "Você atingiu o limite de matérias de hoje. Volte amanhã.",
    "limite_mensal": "Você atingiu o limite de matérias deste mês.",
    "erro_servico": "Não foi possível verificar seu acesso agora. Tente novamente em instantes.",
}


def supabase_configurado() -> bool:
    return bool(segredo("SUPABASE_URL")) and bool(segredo("SUPABASE_SERVICE_KEY"))


def supa_rpc(funcao: str, corpo: dict) -> dict:
    """Chama uma função do banco (criada pelo arquivo supabase_setup.sql)."""
    chave_servico = str(segredo("SUPABASE_SERVICE_KEY"))
    url = str(segredo("SUPABASE_URL")).rstrip("/") + f"/rest/v1/rpc/{funcao}"
    resp = requests.post(
        url, json=corpo, timeout=15,
        headers={"apikey": chave_servico, "Authorization": f"Bearer {chave_servico}",
                 "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


def consultar_codigo(codigo: str):
    """Mostra o que o código libera e quanto já foi usado (sem gastar cota)."""
    if not codigo.strip():
        return None
    try:
        return supa_rpc("status_codigo", {"p_codigo": codigo.strip()})
    except Exception:
        return {"ok": False, "motivo": "erro_servico"}


# -----------------------------------------------------------------------------
# 3. CONFIGURAÇÃO DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Curador de Notícias", page_icon="📰", layout="wide")

if "historico" not in st.session_state:
    st.session_state.historico = []

# -----------------------------------------------------------------------------
# 4. BARRA LATERAL — escolha da versão e verificações
# -----------------------------------------------------------------------------
with st.sidebar:
    pagina = st.radio("Página", ["📰 Gerar matéria", "💳 Planos"])

if pagina == "💳 Planos":
    mostrar_planos()   # desenhado na área principal (fora da barra lateral)
    st.stop()          # não executa o restante do app

with st.sidebar:
    st.divider()
    st.header("⚙️ Configuração")
    chave = st.radio(
        "Versão do programa",
        options=list(VERSOES.keys()),
        format_func=lambda k: VERSOES[k]["titulo"],
    )
    v = VERSOES[chave]
    st.caption(v["descricao"])

    st.markdown("**Etapas desta versão:**")
    for i, etapa in enumerate(v["etapas"], start=1):
        st.markdown(f"{i}. {etapa}")

    st.divider()
    modo_livre = not supabase_configurado()
    codigo = ""
    if modo_livre:
        st.warning("⚠️ Modo teste: sem controle de acesso nem de uso.")
        liberadas = set(VERSOES.keys())
    else:
        codigo = st.text_input("Código de acesso", type="password",
                               help="Enviado após o pagamento do plano.")
        info = consultar_codigo(codigo)
        liberadas = set()
        if info and info.get("ok"):
            liberadas = set(info.get("versoes", []))
            st.success("Código válido ✅")
            st.caption(f"Versões liberadas: {', '.join(sorted(liberadas))}")
            st.caption(f"Matérias no mês: {info.get('usados_mes')}/{info.get('limite_mensal')}  |  "
                       f"hoje: {info.get('usados_dia')}/{info.get('limite_diario')}")
        elif info:
            st.error(MENSAGENS.get(info.get("motivo"), "Código inválido."))

    # Verificações feitas em silêncio (só aparecem se algo estiver errado)
    problemas = []
    if not os.getenv("OPENAI_API_KEY"):
        problemas.append("OPENAI_API_KEY não encontrada (.env local ou Secrets na nuvem).")
    if not (BASE_DIR / f"{v['modulo']}.py").exists():
        problemas.append(f"Arquivo {v['modulo']}.py não encontrado na pasta do app.")
    if v["usa_skills_dir"] and not (BASE_DIR / "skills").exists():
        problemas.append("Pasta 'skills' não encontrada na pasta do app.")

# -----------------------------------------------------------------------------
# 5. ÁREA PRINCIPAL
# -----------------------------------------------------------------------------
st.title("📰 Agente de Curadoria de Notícias")
st.subheader(v["titulo"])

tema = st.text_area(
    "Tema ou manchete da notícia",
    key="tema",  # chave fixa: o texto não se apaga ao trocar de versão
    placeholder="Digite o tema ou a manchete da notícia",
    height=90,
)
st.caption(f"Exemplo: {v['exemplo']}")
gerar = st.button("🚀 Gerar matéria", type="primary")

if gerar:
    if chave not in liberadas:
        st.warning(f"A versão {chave} não está liberada. Digite um código válido na barra "
                   "lateral ou veja os planos (Página → Planos).")
    elif problemas:
        for problema in problemas:
            st.error(problema)
    elif not tema.strip():
        st.error("Digite um tema antes de gerar a matéria.")
    else:
        liberado, motivo = True, ""
        if not modo_livre:
            # Conta a matéria ANTES de rodar (execução que falha também custa na OpenAI)
            try:
                reserva = supa_rpc("reservar_uso", {"p_codigo": codigo.strip(), "p_versao": chave})
                liberado = bool(reserva.get("ok"))
                motivo = MENSAGENS.get(reserva.get("motivo"), "Acesso negado.")
            except Exception:
                liberado, motivo = False, MENSAGENS["erro_servico"]

        if not liberado:
            st.error(motivo)
        else:
            pasta_saida = BASE_DIR / v["saida"]
            antes = listar_md(pasta_saida)
            inicio = time.time()

            try:
                alvo = carregar_objeto(v["modulo"], v["objeto"])
                with st.status("Trabalhando... isso pode levar alguns minutos ⏳", expanded=True) as status:
                    for etapa in v["etapas"]:
                        st.write(f"• {etapa}")
                    resposta = alvo.run(tema.strip())
                    status.update(label="Concluído ✅", state="complete", expanded=False)

                duracao = time.time() - inicio
                texto = extrair_texto(resposta)
                novos = arquivos_novos(antes, listar_md(pasta_saida))

                # Se a resposta veio vazia, usa o arquivo salvo mais recente
                if not texto.strip() and novos:
                    texto = novos[0].read_text(encoding="utf-8", errors="ignore")

                st.session_state.historico.insert(0, {
                    "versao": chave,
                    "tema": tema.strip(),
                    "texto": texto,
                    "duracao": duracao,
                    "arquivos": [str(p) for p in novos],
                })
            except Exception as erro:
                st.error("Algo deu errado durante a execução.")
                st.exception(erro)

# -----------------------------------------------------------------------------
# 6. RESULTADOS (o mais recente aparece primeiro)
# -----------------------------------------------------------------------------
if st.session_state.historico:
    st.divider()
    ultimo = st.session_state.historico[0]
    st.markdown(f"### Resultado mais recente — {ultimo['versao']}")
    st.caption(f"Tema: {ultimo['tema']}  |  Tempo: {ultimo['duracao']:.0f} s")

    aba_materia, aba_arquivos = st.tabs(["📄 Matéria", "💾 Arquivos salvos"])

    with aba_materia:
        if ultimo["texto"].strip():
            st.markdown(ultimo["texto"])
            st.download_button(
                "⬇️ Baixar matéria (.md)",
                data=ultimo["texto"],
                file_name=f"materia_{ultimo['versao']}.md",
                mime="text/markdown",
                key="download_ultimo",
            )
        else:
            st.warning("O agente não devolveu texto. Veja a aba 'Arquivos salvos'.")

    with aba_arquivos:
        if not ultimo["arquivos"]:
            st.info("Nenhum arquivo .md novo foi salvo nesta execução.")
        for i, caminho in enumerate(ultimo["arquivos"]):
            p = Path(caminho)
            with st.expander(f"📁 {p.name}"):
                conteudo = p.read_text(encoding="utf-8", errors="ignore")
                st.markdown(conteudo)
                st.download_button(
                    "⬇️ Baixar", data=conteudo, file_name=p.name,
                    mime="text/markdown", key=f"download_arquivo_{i}",
                )

    if len(st.session_state.historico) > 1:
        with st.expander("🕘 Execuções anteriores (nesta sessão)"):
            for j, item in enumerate(st.session_state.historico[1:], start=1):
                st.markdown(f"**{item['versao']}** — {item['tema']} ({item['duracao']:.0f} s)")
                with st.expander("Ver matéria", expanded=False):
                    st.markdown(item["texto"] or "_(vazio)_")