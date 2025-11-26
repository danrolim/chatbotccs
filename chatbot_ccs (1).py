# chatbot_ccs.py
# Protótipo de chatbot FAQ para o Setor de Gestão de Pessoas (CCS/UFPB)
# Execução: python chatbot_ccs.py
# Requisitos: Python 3 e a biblioteca Flask (pip install Flask)

import sys
import re
import unicodedata
from difflib import SequenceMatcher

# Importações para a interface web
from flask import Flask, request, jsonify, render_template

BANNER = '''
====================================================
  Chatbot - Atendimento CCS/UFPB (Protótipo CLI)
  Pergunte sobre: férias, plano de trabalho, afastamentos,
  atendimento, horário, documentos, contatos...

  Comandos úteis: "menu", "opções", "listar", "sair"
====================================================
'''


def normalize(text: str) -> str:
    """Normaliza texto para comparação: minúsculas, sem acentos,
    remove pontuação simples e espaços extras."""
    if not text:
        return ""
    text = text.lower().strip()
    # remove acentos
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    # remove pontuação simples
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # colapsa espaços
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Base de conhecimento inicial (mock) — substituir/expandir conforme documentos da PROGEP/UFPB
KB = [
    {
        "id": "ferias_basico",
        "tags": ["ferias", "férias", "marcar ferias", "periodo aquisitivo"],
        "patterns": [
            "como marcar ferias",
            "quando posso tirar ferias",
            "ferias servidor ccs",
            "calendario de ferias",
            "prazo ferias",
        ],
        "answer": (
            "FÉRIAS — Informações básicas:\\n"
            "- O agendamento segue o calendário institucional.\\n"
            "- A solicitação deve ser registrada no sistema SIGRH conforme orientações da PROGEP.\\n"
            "- Recomenda-se antecedência mínima de 30 dias (antes do fechamento da folha), conforme a norma interna.\\n"
            "Consulte o manual/portais oficiais da PROGEP/UFPB para detalhes e prazos (https://www.progep.ufpb.br/progep/colecoes/manual-do-servidor-1)."
        ),
    },
    {
        "id": "plano_trabalho",
        "tags": ["plano de trabalho", "plano", "pt", "atividades", "registro"],
        "patterns": [
            "como enviar plano de trabalho",
            "onde registrar plano de trabalho",
            "prazo do plano de trabalho",
            "modelo de plano de trabalho",
        ],
        "answer": (
            "PLANO DE TRABALHO — Diretrizes:\\n"
            "- O envio é feito via SEI usando o modelo oficial.\\n"
            "- Verifique o manual da PROGEP/UFPB para campos obrigatórios e periodicidade.\\n"
            "- Guarde o comprovante de protocolo.\\n"
            "Para links e modelos, consulte o site da PROGEP (https://www.progep.ufpb.br/progep/colecoes/manual-do-servidor-1)."
        ),
    },
    {
        "id": "afastamentos",
        "tags": ["afastamento", "licenca", "licença", "saude", "capacitação"],
        "patterns": [
            "como solicitar afastamento",
            "afastamento para capacitacao",
            "licenca medica",
            "documentos para afastamento",
        ],
        "answer": (
            "AFASTAMENTOS — Passos gerais:\\n"
            "- Verifique o tipo (capacitação, saúde, interesse, etc.).\\n"
            "- Anexe a documentação exigida conforme o tipo de afastamento.\\n"
            "- Protocole no SIPAC e acompanhe os prazos.\\n"
            "As regras completas constam no portal da PROGEP/UFPB. Disponível no manual do servidor: https://www.progep.ufpb.br/progep/colecoes/manual-do-servidor-1"
        ),
    },
    {
        "id": "horario_contato",
        "tags": ["horario", "horário", "contato", "email", "e-mail", "atendimento"],
        "patterns": [
            "qual horario de atendimento",
            "como entrar em contato",
            "email do setor",
            "telefone do setor",
        ],
        "answer": (
            "ATENDIMENTO — Contatos e horários (protótipo):\\n"
            "- Horário padrão: dias úteis, conforme expediente do CCS (07:00 às 17:00 horas).\\n"
            "- Priorize o atendimento institucional (e-mail setorial: rhccs@ccs.ufpb.br; Ramal: 3216-7236).\\n"
            "Para demandas complexas, descreva o caso e anexe documentos no SEI."
        ),
    },
    {
        "id": "documentos_publicos",
        "tags": ["documento", "documentos", "base de dados", "norma", "manual", "faq"],
        "patterns": [
            "onde estao os documentos",
            "documentos publicos",
            "manual da PROGEP",
            "base de conhecimento",
        ],
        "answer": (
            "DOCUMENTOS — Acesso público:\\n"
            "- Os documentos/FAQs estão disponíveis no portal da Pró-Reitoria de Gestão de Pessoas (PROGEP/UFPB).\\n"
            "- Utilize as buscas por tema (férias, plano de trabalho, afastamentos) e verifique as versões atualizadas.\\n"
            "- Acesse o manual do servidor na página: https://www.progep.ufpb.br/progep/colecoes/manual-do-servidor-1."
        ),
    },
    {
        "id": "fallback",
        "tags": [],
        "patterns": [],
        "answer": (
            "Não encontrei uma resposta direta para sua pergunta.\\n"
            "Você pode tentar:\\n"
            "1) digitar 'menu' para ver opções; ou\\n"
            "2) reescrever com mais detalhes; ou\\n"
            "3) encaminhar ao atendimento humano via e-mail institucional."
        ),
    },
]

MENU = [
    ("Férias", "Pergunte sobre períodos, prazos e agendamento."),
    ("Plano de trabalho", "Envio via SEI, modelos e prazos."),
    ("Afastamentos", "Tipos, documentos e protocolo."),
    ("Atendimento/Contato", "Horário e canais institucionais."),
    ("Documentos públicos", "Onde localizar manuais e normas (PROGEP/UFPB)."),
]


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def find_best_answer(user_input: str) -> str:
    q = normalize(user_input)
    if not q:
        return "Digite sua dúvida ou 'menu' para ver opções."

    # 1) correspondência por TAG (palavra-chave direta)
    for item in KB:
        for tag in item["tags"]:
            if normalize(tag) in q:
                return item["answer"]

    # 2) similaridade com padrões
    best_score = 0.0
    best_item = None
    for item in KB:
        for patt in item["patterns"]:
            score = similar(q, normalize(patt))
            if score > best_score:
                best_score = score
                best_item = item

    if best_item and best_score >= 0.60:
        return best_item["answer"]

    # 3) fallback
    return next(x for x in KB if x["id"] == "fallback")["answer"]


# --- INTEGRAÇÃO WEB COM FLASK ---

app = Flask(__name__)


# Rota para a página inicial
@app.route('/')
def index():
    """Renderiza o template HTML da interface do chat."""
    return render_template('index.html')


# Rota para a API do chatbot (processa a mensagem)
@app.route('/chat', methods=['POST'])
def chat():
    """Recebe a mensagem do usuário e retorna a resposta do chatbot."""
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({"answer": "Por favor, digite sua pergunta."})

    normalized_message = normalize(user_message)

    # Processamento de comandos especiais na web
    if normalized_message in {"sair", "exit", "tchau"}:
        return jsonify({"answer": "Obrigado por usar o Chatbot. Até logo!"})

    if normalized_message in {"menu", "opcoes", "opções", "listar"}:
        menu_text = "\\n=== MENU DE TÓPICOS ===\\n"
        for i, (titulo, desc) in enumerate(MENU, 1):
            # Usamos \\n para que o JavaScript no frontend possa converter para <br>
            menu_text += f"{i}. {titulo} — {desc}\\n"
        menu_text += "=======================\\n"
        return jsonify({"answer": menu_text})

    # Busca a melhor resposta
    answer = find_best_answer(user_message)

    # Adiciona a dica de follow-up se for uma resposta de fallback
    if "Não encontrei" in answer:
        answer += "\\nExemplos: 'como marcar férias', 'plano de trabalho', 'afastamento para capacitação'."

    return jsonify({"answer": answer})


if __name__ == '__main__':
    # Roda o servidor Flask. Acesse http://127.0.0.1:5000/ no seu navegador.
    print(BANNER)  # Mantém o banner no console ao iniciar
    print("Iniciando interface web...")
    print("Acesse: http://127.0.0.1:5000/")
    # O modo debug reinicia o servidor automaticamente ao salvar mudanças no código Python.
    app.run(host='0.0.0.0', debug=True)