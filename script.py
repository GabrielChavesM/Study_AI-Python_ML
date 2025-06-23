import os
import json
import re
import customtkinter as ctk
from tkinter import messagebox, Listbox
from groq import Groq
from dotenv import load_dotenv
import speech_recognition as sr
import threading
import pyttsx3
import queue
import multiprocessing
from datetime import datetime

# Remove conteúdo entre <think></think> das perguntas
def remover_think(texto):
    return re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL).strip()

# Carregar variáveis ambiente
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

import platform

# Verifica se o sistema requer fallback
def safe_tts_engine(self):
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 1.0)

        # Seleciona voz compatível com o idioma escolhido
        idioma = self.lingua
        for voice in engine.getProperty('voices'):
            if idioma == "Português" and ('portugal' in voice.name.lower() or 'brazil' in voice.name.lower()):
                engine.setProperty('voice', voice.id)
                break
            elif idioma == "Inglês" and 'english' in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        return engine
    except Exception as e:
        print(f"[ERRO ao inicializar TTS]: {e}")
        return None

# Inicializar apenas uma vez
tts_engine = None
tts_queue = queue.Queue()

def executar_tts():
    while True:
        try:
            texto = tts_queue.get(block=True)
            if not texto.strip():
                continue

            if tts_engine:
                tts_engine.say(texto)
                tts_engine.runAndWait()

        except Exception as e:
            print(f"[ERRO TTS] {e}")

# Variável global para controlar o processo TTS atual
tts_current_process = None
tts_lock = threading.Lock()

def tts_process(texto_para_ler):
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 1.0)

        for voice in engine.getProperty('voices'):
            if 'portugal' in voice.name.lower() or 'brazil' in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break

        engine.say(texto_para_ler)
        engine.runAndWait()
    except Exception as e:
        print(f"[ERRO TTS subprocesso] {e}")

def tts_check_queue():
    global tts_current_process
    global tts_queue_list

    if tts_current_process is not None:
        if tts_current_process.is_alive():
            return
        else:
            # Processo terminou
            tts_current_process.join()
            tts_current_process = None

    if tts_queue_list:
        texto = tts_queue_list.pop(0)
        tts_current_process = multiprocessing.Process(target=tts_process, args=(texto,), daemon=True)
        tts_current_process.start()

def ler_texto(texto):
    global tts_current_process
    if hasattr(app, 'modo_mudo') and app.modo_mudo:
        return

    with tts_lock:
        # Se já estiver a ler algo, interrompe
        if tts_current_process is not None and tts_current_process.is_alive():
            tts_current_process.terminate()
            tts_current_process.join()
            tts_current_process = None

        # Inicia nova leitura
        tts_current_process = multiprocessing.Process(target=tts_process, args=(texto,), daemon=True)
        tts_current_process.start()


# Diretórios
PROMPTS_DIR = "prompts"
HISTORICOS_DIR = "historicos"
HISTORICOS_GERAIS_DIR = "historicos_gerais"
os.makedirs(PROMPTS_DIR, exist_ok=True)
os.makedirs(HISTORICOS_DIR, exist_ok=True)
os.makedirs(HISTORICOS_GERAIS_DIR, exist_ok=True)

if not os.path.exists(HISTORICOS_GERAIS_DIR):
    print(f"Diretório '{HISTORICOS_GERAIS_DIR}' não existe.")
else:
    print(f"Arquivos no diretório '{HISTORICOS_GERAIS_DIR}': {os.listdir(HISTORICOS_GERAIS_DIR)}")

def listar_prompts():
    return [os.path.splitext(f)[0] for f in os.listdir(PROMPTS_DIR) if f.endswith(".txt")]

def ler_prompt_texto(prompt_path):
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def carregar_historico_json(json_path):
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def salvar_no_historico_json(json_path, role, content):
    historico = carregar_historico_json(json_path)

    if historico and historico[-1]["role"] == role and historico[-1]["content"] == content:
        print("Entrada repetida detectada. Não será salva novamente.")
        return

    for msg in historico:
        if msg["role"] == role and msg["content"] == content:
            return

    historico.append({"role": "user" if role == "user" else "assistant", "content": content})
    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(historico, file, indent=2, ensure_ascii=False)

def obter_resposta_groq(pergunta, prompt_path, historico_path):
    client = Groq(api_key=GROQ_API_KEY)
    # Não carregar histórico para enviar ao prompt, só carregar prompt-base
    prompt_base = ler_prompt_texto(prompt_path)

    mensagens = []
    if prompt_base:
        mensagens.append({"role": "user", "content": prompt_base})
    mensagens.append({"role": "user", "content": pergunta})

    try:
        chat_completion = client.chat.completions.create(
            messages=mensagens,
            model="deepseek-r1-distill-llama-70b"
        )
        resposta_raw = chat_completion.choices[0].message.content.strip()

        # Salvar pergunta e resposta no histórico JSON (para registro)
        salvar_no_historico_json(historico_path, "user", pergunta)
        salvar_no_historico_json(historico_path, "assistant", resposta_raw)

        resposta_limpa = remover_think(resposta_raw)
        return resposta_limpa

    except Exception as e:
        return f"Erro ao acessar a API Groq: {str(e)}"

def parse_pergunta(texto):
    p = re.search(r'\*\*Pergunta:\*\*\s*(.+?)(?=\nA\)|\nB\)|\nC\)|\nD\))', texto, re.DOTALL)
    pergunta = p.group(1).strip() if p else ""

    alternativas = {}
    for letra in ['A', 'B', 'C', 'D']:
        pattern = rf'{letra}\)\s*(.+?)(?=\n[A-D]\)|\n\*\*Resposta correta:\*\*|$)'
        m = re.search(pattern, texto, re.DOTALL)
        if m:
            alternativas[letra] = m.group(1).strip().replace('\n',' ').replace('\r',' ')

    rc = re.search(r'\*\*Resposta correta:\*\*\s*([ABCD])', texto)
    resposta_correta = rc.group(1) if rc else None

    expl = re.search(r'\*\*Explicação:\*\*\s*(.+)', texto, re.DOTALL)
    explicacao = expl.group(1).strip() if expl else ""

    return pergunta, alternativas, resposta_correta, explicacao

def apagar_todos_jsons():
    try:
        for filename in os.listdir(HISTORICOS_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(HISTORICOS_DIR, filename)
                os.remove(filepath)
    except Exception as e:
        print(f"Erro ao apagar arquivos JSON: {e}")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("StudyAI")
        self.geometry("768x768")
        self.resizable(False, False)
        self.modo_mudo = False
        self.dark_mode = True  # Inicialmente no modo escuro
        self.tts_falando = False  # Flag para controlar se TTS está a falar

        self.protocol("WM_DELETE_WINDOW", self.sair)

        self.prompts = listar_prompts()
        if not self.prompts:
            messagebox.showerror("Erro", f"Nenhum prompt encontrado em '{PROMPTS_DIR}'.")
            self.destroy()
            return

        self.dificuldades = ["fácil", "média", "difícil"]
        self.perguntas_respondidas = 0
        self.acertos = 0
        self.historico_path = None
        self.prompt_path = None
        self.prompt_nome = None
        self.dificuldade = None
        self.pergunta_atual = None
        self.resposta_correta_atual = None
        self.explicacao_atual = None
        self.perguntas_geradas = set()
        self.erros = []  # Lista para armazenar perguntas erradas
        self.acertadas = []  # Lista para armazenar perguntas acertadas

        self.create_widgets()
        self.config_states(iniciar=True)

    def bloquear_digitar(self, event):
        return "break"

    def alternar_modo(self):
        self.dark_mode = not self.dark_mode
        ctk.set_appearance_mode("dark" if self.dark_mode else "light")
        self.btn_modo.configure(text="🌙 Dark Mode" if self.dark_mode else "☀️ Light Mode")

    def alternar_mudo(self):
        self.modo_mudo = not self.modo_mudo
        self.btn_mudo.configure(text="🔇 Som Desligado" if self.modo_mudo else "🔊 Som Ligado")

    def atualizar_aproveitamento(self):
        if self.perguntas_respondidas > 0:
            aproveitamento = int((self.acertos / self.perguntas_respondidas) * 100)
            self.label_aproveitamento.configure(
                text=f"Está com {aproveitamento}% de aproveitamento até agora" if self.lingua == "Português" else f"You currently have {aproveitamento}% accuracy."
            )
            self.progress.set(self.perguntas_respondidas / 8)

    def create_widgets(self):
        ctk.CTkLabel(self, text="Escolha a matéria:").pack(pady=(10, 0))
        self.combo_prompt = ctk.CTkComboBox(self, values=self.prompts, width=600)
        self.combo_prompt.pack(pady=(0, 10))
        self.combo_prompt.set(self.prompts[0])
        self.combo_prompt.bind("<Key>", self.bloquear_digitar)

        ctk.CTkLabel(self, text="Escolha a dificuldade:").pack(pady=(0, 0))
        self.combo_dificuldade = ctk.CTkComboBox(self, values=self.dificuldades, width=600)
        self.combo_dificuldade.pack(pady=(0, 10))
        self.combo_dificuldade.set(self.dificuldades[1])
        self.combo_dificuldade.bind("<Key>", self.bloquear_digitar)

        ctk.CTkLabel(self, text="Escolha a língua:").pack(pady=(0, 0))
        self.combo_lingua = ctk.CTkComboBox(self, values=["Português", "English"], width=600)
        self.combo_lingua.pack(pady=(0, 10))
        self.combo_lingua.set("Português")  # Língua padrão
        self.combo_lingua.bind("<Key>", self.bloquear_digitar)

        self.btn_iniciar = ctk.CTkButton(self, text="Iniciar Quiz", command=self.iniciar_quiz)
        self.btn_iniciar.pack(pady=(0, 15))

        self.text_chat = ctk.CTkTextbox(self, width=680, height=300, state="disabled", wrap="word")
        self.text_chat.pack(pady=10)

        self.progress = ctk.CTkProgressBar(self, width=680)
        self.progress.set(0.0)
        self.progress.pack(pady=(5, 2))

        self.label_aproveitamento = ctk.CTkLabel(self, text="Está com 0% de aproveitamento até agora")
        self.label_aproveitamento.pack(pady=(0, 10))

        frame_resposta = ctk.CTkFrame(self)
        frame_resposta.pack(pady=(5, 10), fill="x", padx=10)

        self.entry_resposta = ctk.CTkEntry(frame_resposta, width=600, placeholder_text="Digite a resposta (A, B, C ou D)")
        self.entry_resposta.pack(side="left", padx=(0, 5), fill="x", expand=True)
        self.entry_resposta.bind("<Return>", lambda event: self.enviar_resposta())

        self.btn_enviar = ctk.CTkButton(frame_resposta, text="Enviar", command=self.enviar_resposta)
        self.btn_enviar.pack(side="right")

        frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes.pack(pady=(5, 10))

        # Botão de Som Ligado/Desligado
        self.btn_mudo = ctk.CTkButton(frame_botoes, text="🔊 Som Ligado", command=self.alternar_mudo, width=150, height=30)
        self.btn_mudo.pack(side="left", padx=(0, 10))

        # Botão de Dark/Light Mode
        self.btn_modo = ctk.CTkButton(frame_botoes, text="🌙 Dark Mode", command=self.alternar_modo, width=150, height=30)
        self.btn_modo.pack(side="left", padx=(0, 10))

        # Botão de Ver Histórico
        self.btn_historico = ctk.CTkButton(frame_botoes, text="Ver Histórico", command=self.abrir_historico, width=150, height=30)
        self.btn_historico.pack(side="left", padx=(0, 10))        

        # Botão de Sair
        self.btn_sair = ctk.CTkButton(frame_botoes, text="Sair", fg_color="red", command=self.sair, width=150, height=30)
        self.btn_sair.pack(side="left", padx=(0, 10))

        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.pack(pady=(0, 10))

    def config_states(self, iniciar=False, quiz_ativo=False):
        self.combo_prompt.configure(state="normal" if iniciar else "disabled")
        self.combo_dificuldade.configure(state="normal" if iniciar else "disabled")
        self.btn_iniciar.configure(state="normal" if iniciar else "disabled")
        self.entry_resposta.configure(state="normal" if quiz_ativo else "disabled")
        self.btn_enviar.configure(state="normal" if quiz_ativo else "disabled")

    def iniciar_quiz(self):
        self.prompt_nome = os.path.splitext(self.combo_prompt.get())[0]
        self.prompt_path = os.path.join(PROMPTS_DIR, self.combo_prompt.get())
        self.dificuldade = self.combo_dificuldade.get()
        self.lingua = self.combo_lingua.get()  # Salvar a língua escolhida
        self.historico_path = os.path.join(HISTORICOS_DIR, f"{self.prompt_nome}_{self.dificuldade}_{self.lingua}.json")

        self.perguntas_respondidas = 0
        self.acertos = 0
        self.erros = []
        self.acertadas = []
        self.perguntas_geradas = set()
        self.perguntas_geradas.clear()
        self.entry_resposta.delete(0, "end")

        with open(self.historico_path, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

        self.text_chat.configure(state="normal")
        idioma_texto = f"Quiz iniciado!\nTema: {self.prompt_nome.replace('_', ' ')}\nDificuldade: {self.dificuldade}\nResponda 8 perguntas.\n\n"
        if self.lingua == "Inglês":
            idioma_texto = f"Quiz started!\nTopic: {self.prompt_nome.replace('_', ' ')}\nDifficulty: {self.dificuldade}\nAnswer 8 questions.\n\n"
        self.text_chat.insert("end", idioma_texto)
        self.text_chat.configure(state="disabled")

        # Reset barra e label aproveitamento
        self.progress.set(0.0)
        self.label_aproveitamento.configure(text="Está com 0% de aproveitamento até agora" if self.lingua == "Português" else "You currently have 0% accuracy.")

        self.config_states(iniciar=False, quiz_ativo=True)
        self.gerar_pergunta_async()

    def gerar_pergunta_async(self, tentativas=0):
        MAX_TENTATIVAS = 5
        if tentativas > MAX_TENTATIVAS:
            mensagem_erro = "Não foi possível gerar uma pergunta nova após várias tentativas. Tente reiniciar o quiz." if self.lingua == "Português" else "Failed to generate a new question after several attempts. Try restarting the quiz."
            self.atualizar_chat(mensagem_erro, "assistant")
            self.status_label.configure(text="")
            return

        # Bloqueia a entrada de respostas enquanto a pergunta está sendo gerada
        self.entry_resposta.configure(state="disabled")
        self.btn_enviar.configure(state="disabled")
        self.status_label.configure(text="A gerar pergunta, aguarde..." if self.lingua == "Português" else "Generating question, please wait...")

        def worker():
            pergunta_texto = (
                f"Crie uma pergunta de múltipla escolha com 4 alternativas (A, B, C, D) sobre "
                f"'{self.prompt_nome.replace('_', ' ')}' de nível {self.dificuldade}. "
                f"Use este formato fixo:\n\n"
                f"**Pergunta:** [texto da pergunta em {'português' if self.lingua == "Português" else 'inglês'}, apenas com texto simples]\n"
                f"A) [opção A]\nB) [opção B]\nC) [opção C]\nD) [opção D]\n\n"
                f"**Resposta correta:** [A|B|C|D]\n"
                f"**Explicação:** [texto explicativo]\n\n"
                f"Importante: Apenas texto simples, sem formatação matemática ou Markdown, evite usar \( \) "
                f"e não repita perguntas já feitas neste quiz."
            )

            resposta_ia = obter_resposta_groq(pergunta_texto, self.prompt_path, self.historico_path)
            pergunta, alternativas, resposta_correta, explicacao = parse_pergunta(resposta_ia)

            if not pergunta or not alternativas or not resposta_correta:
                self.after(100, lambda: self.gerar_pergunta_async(tentativas + 1))
                return

            # Verifica se a pergunta já foi feita neste quiz
            pergunta_simplificada = re.sub(r'[^a-zA-Z0-9]', '', pergunta.lower())
            for pergunta_existente in self.perguntas_geradas:
                existente_simplificada = re.sub(r'[^a-zA-Z0-9]', '', pergunta_existente.lower())
                if pergunta_simplificada in existente_simplificada or existente_simplificada in pergunta_simplificada:
                    self.after(100, lambda: self.gerar_pergunta_async(tentativas + 1))
                    return

            # Se chegou aqui, é uma pergunta nova
            self.perguntas_geradas.add(pergunta)

            def update_ui():
                self.pergunta_atual = pergunta
                self.resposta_correta_atual = resposta_correta.upper()
                self.explicacao_atual = explicacao

                texto_exibir = f"Pergunta {self.perguntas_respondidas + 1}:\n{pergunta}\n" if self.lingua == "Português" else f"Question {self.perguntas_respondidas + 1}:\n{pergunta}\n"
                for letra in ['A', 'B', 'C', 'D']:
                    texto_exibir += f"{letra}) {alternativas.get(letra, '')}\n"

                self.text_chat.configure(state="normal", font=("Arial", 14))  # Define a fonte e o tamanho
                self.atualizar_chat(texto_exibir, "assistant")
                self.status_label.configure(text="")

                # Ler a pergunta e as alternativas automaticamente
                texto_para_voz = f"Pergunta {self.perguntas_respondidas + 1}. {pergunta}. " if self.lingua == "Português" else f"Question {self.perguntas_respondidas + 1}. {pergunta}. "
                for letra in ['A', 'B', 'C', 'D']:
                    texto_para_voz += f"Opção {letra}: {alternativas.get(letra, '')}. " if self.lingua == "Português" else f"Option {letra}: {alternativas.get(letra, '')}. "
                ler_texto(texto_para_voz)

                # Libera a entrada de respostas após a pergunta ser exibida
                self.entry_resposta.configure(state="normal")
                self.btn_enviar.configure(state="normal")

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def atualizar_chat(self, texto, remetente):
        self.text_chat.configure(state="normal")
        prefixo = "Você: " if remetente == "user" else "IA: "
        self.text_chat.insert("end", prefixo + texto + "\n\n")
        self.text_chat.see("end")
        self.text_chat.configure(state="disabled")

    def enviar_resposta(self):
        resposta_usuario = self.entry_resposta.get().strip().upper()
        if resposta_usuario not in ['A', 'B', 'C', 'D']:
            messagebox.showwarning("Resposta inválida", "Digite A, B, C ou D para responder." if self.lingua == "Português" else "Enter A, B, C, or D to respond.")
            return

        self.entry_resposta.delete(0, "end")
        self.atualizar_chat(resposta_usuario, "user")

        correta = (resposta_usuario == self.resposta_correta_atual)
        texto_correcao = f"Resposta correta: {self.resposta_correta_atual}\nExplicação: {self.explicacao_atual}" if self.lingua == "Português" else f"Correct answer: {self.resposta_correta_atual}\nExplanation: {self.explicacao_atual}"
        texto_feedback = f"{'Acertou!' if correta else 'Errou.'} {texto_correcao}" if self.lingua == "Português" else f"{'Correct!' if correta else 'Wrong.'} {texto_correcao}"

        self.atualizar_chat(texto_feedback, "assistant")
        ler_texto(texto_feedback)

        # Atualiza o número de perguntas respondidas
        self.perguntas_respondidas += 1
        if correta:
            self.acertos += 1

        # Atualiza o aproveitamento em tempo real
        self.atualizar_aproveitamento()

        # Calcula o tempo necessário para o TTS com base no número de palavras
        palavras = len(texto_feedback.split())
        tempo_tts = int(palavras * 0.8 * 1000)  # Converte para milissegundos

        # Bloqueia novas respostas pelo tempo calculado
        self.entry_resposta.configure(state="disabled")
        self.btn_enviar.configure(state="disabled")

        def permitir_proxima():
            self.entry_resposta.configure(state="normal")
            self.btn_enviar.configure(state="normal")
            if self.perguntas_respondidas >= 8:
                self.finalizar_quiz()
            else:
                self.gerar_pergunta_async()

        self.after(tempo_tts, permitir_proxima)

    def gerar_feedback_final(self):
        # Prepara o contexto para a IA gerar um feedback personalizado
        contexto_feedback = (
            f"O aluno respondeu a um quiz sobre {self.prompt_nome.replace('_', ' ')} com dificuldade {self.dificuldade}. "
            f"Acertou {self.acertos} de 8 perguntas. Aqui está uma análise detalhada:\n\n"
            f"Perguntas erradas:\n"
        )
        
        for i, erro in enumerate(self.erros, 1):
            contexto_feedback += (
                f"{i}. Pergunta: {erro['pergunta']}\n"
                f"   Resposta do aluno: {erro['resposta_usuario']}\n"
                f"   Resposta correta: {erro['resposta_correta']}\n"
                f"   Explicação: {erro['explicacao']}\n\n"
            )
        
        contexto_feedback += "\nPerguntas acertadas:\n"
        for i, acerto in enumerate(self.acertadas, 1):
            contexto_feedback += (
                f"{i}. Pergunta: {acerto['pergunta']}\n"
                f"   Explicação: {acerto['explicacao']}\n\n"
            )
        
        contexto_feedback += (
            "\n Não use formatação Markdown, não use asteriscos para negrito, apenas texto simples. Evite usar \( \) e não repita perguntas já feitas neste quiz."
            "\nPor favor, forneça um feedback formatado da seguinte maneira:\n"
            "1. Análise Geral do Desempenho:\n"
            "\n Não use formatação Markdown, não use asteriscos para negrito, apenas texto simples. Evite usar \( \) e não repita perguntas já feitas neste quiz."
            "   [Uma frase curta]\n\n"
            "2. Principais Temas que Precisa Reforçar:\n"
            "\n Não use formatação Markdown, não use asteriscos para negrito, apenas texto simples. Evite usar \( \) e não repita perguntas já feitas neste quiz."
            "   - [Enumere os temas e o que melhorar]\n\n"
            "3. Sugestões Específicas de Estudo:\n"
            "\n Não use formatação Markdown, não use asteriscos para negrito, apenas texto simples. Evite usar \( \) e não repita perguntas já feitas neste quiz."
            "   - [Indique matérias boas para melhorar os temas a reforçar]\n\n"
            "4. Reconhecimento dos Pontos Fortes:\n"
            "\n Não use formatação Markdown, não use asteriscos para negrito, apenas texto simples. Evite usar \( \) e não repita perguntas já feitas neste quiz."
            "   - [Destaque os pontos fortes que podem precisar de menos estudo]\n\n"
            "5. Frase Motivacional:\n"
            "\n Não use formatação Markdown, não use asteriscos para negrito, apenas texto simples. Evite usar \( \) e não repita perguntas já feitas neste quiz."
            "   [Uma frase motivacional para encorajar o aluno]\n"
            "\nUse uma linguagem amigável e encorajadora, como se fosse um professor que quer ajudar o aluno a melhorar."
            "\n Não use formatação Markdown, apenas texto simples. Evite usar \( \) e não repita perguntas já feitas neste quiz."
        )
        
        return obter_resposta_groq(contexto_feedback, self.prompt_path, self.historico_path)
    
    def salvar_desempenho(self):
        historico_desempenho_path = os.path.join(HISTORICOS_GERAIS_DIR, f"historico_desempenho_{self.prompt_nome}.json")
        historico = carregar_historico_json(historico_desempenho_path)

        def obter_tema_ia(explicacoes):
            # Envia as explicações para a IA e solicita os temas
            prompt_tema = (
                "\n Não use formatação Markdown, apenas texto simples. Evite usar \( \) e não repita perguntas já feitas neste quiz."
                "Identifique o tema principal de cada explicação abaixo e retorne uma lista de temas. "
                "\n Não use formatação Markdown, apenas texto simples. Evite usar \( \) e não repita perguntas já feitas neste quiz."
                "Os temas devem ser curtos e claros, como 'Adição', 'Subtração', 'Multiplicação', 'Divisão', etc.\n\n"
                "\n Não use formatação Markdown, apenas texto simples. Evite usar \( \) e não repita perguntas já feitas neste quiz."
                "Explicações:\n" + "\n".join([f"- {exp}" for exp in explicacoes])
            )
            resposta = obter_resposta_groq(prompt_tema, self.prompt_path, self.historico_path)
            temas = [tema.strip() for tema in resposta.split("\n") if tema.strip()]
            return temas

        explicacoes_erradas = [erro["explicacao"] for erro in self.erros]
        explicacoes_acertadas = [acerto["explicacao"] for acerto in self.acertadas]

        temas_errados = obter_tema_ia(explicacoes_erradas)
        temas_acertados = obter_tema_ia(explicacoes_acertadas)

        novo_registro = {
            "data": datetime.now().strftime("%Y-%m-%d"),  # Apenas a data, sem horas
            "dificuldade": self.dificuldade,
            "acertos": self.acertos,
            "total_perguntas": 8,
            "aproveitamento": int((self.acertos / 8) * 100),
            "temas_errados": list(set(temas_errados)),  # Remover duplicatas
            "temas_acertados": list(set(temas_acertados))  # Remover duplicatas
        }

        historico.append(novo_registro)

        # Salvar histórico geral
        with open(historico_desempenho_path, "w", encoding="utf-8") as file:
            json.dump(historico, file, indent=2, ensure_ascii=False)

        # Atualizar histórico geral consolidado
        self.atualizar_historico_geral(historico_desempenho_path)

    def atualizar_historico_geral(self, historico_desempenho_path):
        historico = carregar_historico_json(historico_desempenho_path)

        total_acertos = sum([registro["acertos"] for registro in historico])
        total_perguntas = sum([registro["total_perguntas"] for registro in historico])
        aproveitamento_geral = int((total_acertos / total_perguntas) * 100) if total_perguntas > 0 else 0

        historico_geral_path = os.path.join(HISTORICOS_GERAIS_DIR, f"historico_geral_{self.prompt_nome}.txt")
        with open(historico_geral_path, "w", encoding="utf-8") as file:
            file.write(f"Histórico de Desempenho - {self.prompt_nome}\n\n")
            for registro in historico:
                file.write(
                    f"Data: {registro['data']}\n"
                    f"Dificuldade: {registro['dificuldade']}\n"
                    f"Acertos: {registro['acertos']} de {registro['total_perguntas']}\n"
                    f"Aproveitamento: {registro['aproveitamento']}%\n"
                    f"Temas a Estudar: {', '.join(registro['temas_errados'])}\n"
                    f"Temas Acertados: {', '.join(registro['temas_acertados'])}\n\n"
                    "---------------------------\n\n"
                )
            file.write(f"Histórico geral:\n")
            file.write(f"Acertos: {total_acertos} de {total_perguntas}\n")
            file.write(f"Aproveitamento: {aproveitamento_geral}%\n")

    def abrir_historico(self):
        # Listar os arquivos de histórico disponíveis
        historicos_disponiveis = [
            f.replace("historico_geral_", "").replace(".txt", "")
            for f in os.listdir(HISTORICOS_GERAIS_DIR)
            if f.startswith("historico_geral_") and f.endswith(".txt")
        ]

        if not historicos_disponiveis:
            messagebox.showinfo("Histórico de Desempenho", "Não há históricos registrados.")
            return

        # Criar janela para selecionar o histórico
        janela_selecao = ctk.CTkToplevel(self)
        janela_selecao.title("Selecionar Histórico")
        janela_selecao.geometry("400x300")

        ctk.CTkLabel(janela_selecao, text="Escolha o histórico para visualizar:").pack(pady=(10, 0))

        # Usar Listbox para exibir os históricos disponíveis
        lista_historicos = Listbox(janela_selecao, width=50, height=10)
        lista_historicos.pack(pady=(10, 10))

        for historico in historicos_disponiveis:
            lista_historicos.insert("end", historico)

        def abrir_historico_selecionado():
            selecionado = lista_historicos.get(lista_historicos.curselection())
            if not selecionado:
                messagebox.showwarning("Aviso", "Nenhum histórico foi selecionado.")
                return

            historico_geral_path = os.path.join(HISTORICOS_GERAIS_DIR, f"historico_geral_{selecionado}.txt")

            if not os.path.exists(historico_geral_path):
                messagebox.showinfo("Histórico de Desempenho", f"Não há histórico registrado para a matéria '{selecionado}'.")
                return

            janela_historico = ctk.CTkToplevel(self)
            janela_historico.title(f"Histórico de Desempenho - {selecionado}")
            janela_historico.geometry("600x400")

            text_historico = ctk.CTkTextbox(janela_historico, width=580, height=380, wrap="word")
            text_historico.pack(pady=10)

            with open(historico_geral_path, "r", encoding="utf-8") as file:
                texto_exibir = file.read()

            text_historico.insert("end", texto_exibir)
            text_historico.configure(state="disabled")

            janela_selecao.destroy()

        btn_abrir = ctk.CTkButton(janela_selecao, text="Abrir Histórico", command=abrir_historico_selecionado)
        btn_abrir.pack(pady=(10, 10))

    def finalizar_quiz(self):
        # Primeiro mostra o resumo básico
        texto_final = f"Quiz finished! You answered {self.acertos} out of 8 questions correctly. Accuracy: {int((self.acertos / 8) * 100)}%." if self.lingua == "Inglês" else f"Quiz finalizado! Você acertou {self.acertos} de 8 perguntas. Aproveitamento: {int((self.acertos / 8)*100)}%."
        self.atualizar_chat(texto_final, "assistant")
        ler_texto(texto_final)

        # Salva o desempenho no histórico
        self.salvar_desempenho()

        # Mostrar o feedback detalhado
        self.status_label.configure(text="Generating personalized feedback..." if self.lingua == "Inglês" else "A gerar feedback personalizado...")
        def gerar_e_exibir_feedback():
            feedback = self.gerar_feedback_final()
            self.after(0, lambda: self.atualizar_chat(feedback, "assistant"))
            self.after(0, lambda: ler_texto(feedback))
            self.after(0, lambda: self.status_label.configure(text=""))
            self.after(0, lambda: self.config_states(iniciar=True, quiz_ativo=False))
        threading.Thread(target=gerar_e_exibir_feedback, daemon=True).start()

    def sair(self):
        if messagebox.askyesno("Sair", "Deseja realmente sair?"):
            apagar_todos_jsons()
            self.destroy()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()