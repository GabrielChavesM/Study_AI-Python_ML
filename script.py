import os
import json
import re
import customtkinter as ctk
from tkinter import messagebox
from groq import Groq
from dotenv import load_dotenv
import speech_recognition as sr
import threading
import pyttsx3
import queue
import multiprocessing

# Remove conteúdo entre <think></think>
def remover_think(texto):
    return re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL).strip()

# Carregar variáveis ambiente
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

import platform

# Verifica se o sistema requer fallback
def safe_tts_engine():
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 1.0)

        # Seleciona voz compatível com pt
        for voice in engine.getProperty('voices'):
            if 'portugal' in voice.name.lower() or 'brazil' in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        return engine
    except Exception as e:
        print(f"[ERRO ao inicializar TTS]: {e}")
        return None

# Inicializar apenas uma vez
tts_engine = safe_tts_engine()
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
            # Processo ainda rodando, espera terminar
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
        # Se já estiver lendo algo, interrompe
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
os.makedirs(PROMPTS_DIR, exist_ok=True)
os.makedirs(HISTORICOS_DIR, exist_ok=True)

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
        self.geometry("720x700")
        self.resizable(False, False)
        self.modo_mudo = False
        self.dark_mode = True  # Inicialmente no modo escuro
        self.tts_falando = False  # Flag para controlar se TTS está falando

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

        self.btn_iniciar = ctk.CTkButton(self, text="Iniciar Quiz", command=self.iniciar_quiz)
        self.btn_iniciar.pack(pady=(0, 15))

        self.text_chat = ctk.CTkTextbox(self, width=680, height=300, state="disabled", wrap="word")
        self.text_chat.pack(pady=10)

        self.progress = ctk.CTkProgressBar(self, width=680)
        self.progress.set(0.0)
        self.progress.pack(pady=(5, 2))

        self.label_aproveitamento = ctk.CTkLabel(self, text="Você está com 0% de aproveitamento até agora")
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

        self.btn_mudo = ctk.CTkButton(frame_botoes, text="🔊 Som Ligado", command=self.alternar_mudo)
        self.btn_mudo.pack(side="left", padx=(0, 10))

        self.btn_modo = ctk.CTkButton(frame_botoes, text="🌙 Dark Mode", command=self.alternar_modo)  # Botão para alternar modo
        self.btn_modo.pack(side="left", padx=(0, 10))

        self.btn_sair = ctk.CTkButton(frame_botoes, text="Sair", fg_color="red", command=self.sair)
        self.btn_sair.pack(side="left")

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
        self.historico_path = os.path.join(HISTORICOS_DIR, f"{self.prompt_nome}_{self.dificuldade}.json")

        self.perguntas_respondidas = 0
        self.acertos = 0
        self.perguntas_geradas.clear()
        self.entry_resposta.delete(0, "end")

        with open(self.historico_path, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

        self.text_chat.configure(state="normal")
        self.text_chat.delete("1.0", "end")
        self.text_chat.insert("end", f"Quiz iniciado!\nTema: {self.prompt_nome.replace('_', ' ')}\nDificuldade: {self.dificuldade}\nResponda 8 perguntas.\n\n")
        self.text_chat.configure(state="disabled")

        # Reset barra e label aproveitamento
        self.progress.set(0.0)
        self.label_aproveitamento.configure(text="Você está com 0% de aproveitamento até agora")

        self.config_states(iniciar=False, quiz_ativo=True)
        self.gerar_pergunta_async()

    def gerar_pergunta_async(self, tentativas=0):
        MAX_TENTATIVAS = 5
        if tentativas > MAX_TENTATIVAS:
            self.atualizar_chat("Não foi possível gerar uma pergunta nova após várias tentativas. Tente reiniciar o quiz.", "assistant")
            self.status_label.configure(text="")
            return

        self.status_label.configure(text="A gerar pergunta, aguarde...")

        def worker():
            pergunta_texto = (f"Crie uma pergunta de múltipla escolha com 4 alternativas (A, B, C, D) sobre "
                              f"'{self.prompt_nome.replace('_', ' ')}' de nível {self.dificuldade}. "
                              f"Use este formato fixo:\n\n"
                              f"**Pergunta:** [texto da pergunta em português, apenas com texto simples]\n"
                              f"A) [opção A]\nB) [opção B]\nC) [opção C]\nD) [opção D]\n\n"
                              f"**Resposta correta:** [A|B|C|D]\n"
                              f"**Explicação:** [texto explicativo]\n\n"
                              f"Importante: Apenas texto simples, sem formatação matemática ou Markdown, evite usar \( \)")

            resposta_ia = obter_resposta_groq(pergunta_texto, self.prompt_path, self.historico_path)
            pergunta, alternativas, resposta_correta, explicacao = parse_pergunta(resposta_ia)

            if not pergunta or not alternativas or not resposta_correta:
                self.after(100, lambda: self.gerar_pergunta_async(tentativas + 1))
                return

            if pergunta in self.perguntas_geradas:
                self.after(100, lambda: self.gerar_pergunta_async(tentativas + 1))
                return
            else:
                self.perguntas_geradas.add(pergunta)

            def update_ui():
                self.pergunta_atual = pergunta
                self.resposta_correta_atual = resposta_correta.upper()
                self.explicacao_atual = explicacao

                texto_exibir = f"Pergunta {self.perguntas_respondidas + 1}:\n{pergunta}\n"
                for letra in ['A', 'B', 'C', 'D']:
                    texto_exibir += f"{letra}) {alternativas.get(letra, '')}\n"

                self.atualizar_chat(texto_exibir, "assistant")
                self.status_label.configure(text="")

                # Ler a pergunta e as alternativas automaticamente
                texto_para_voz = f"Pergunta {self.perguntas_respondidas + 1}. {pergunta}. "
                for letra in ['A', 'B', 'C', 'D']:
                    texto_para_voz += f"Opção {letra}: {alternativas.get(letra, '')}. "
                ler_texto(texto_para_voz)

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def atualizar_chat(self, texto, remetente):
        self.text_chat.configure(state="normal")
        prefixo = "Você: " if remetente == "user" else "IA: "
        self.text_chat.insert("end", prefixo + texto + "\n\n")
        self.text_chat.see("end")
        self.text_chat.configure(state="disabled")

    def enviar_resposta(self):
        # Se estiver bloqueado, não faz nada
        if hasattr(self, 'aguardando_proxima') and self.aguardando_proxima:
            messagebox.showinfo("Aguarde", "Aguarde o fim da leitura antes de enviar outra resposta.")
            return

        resposta_usuario = self.entry_resposta.get().strip().upper()
        if resposta_usuario not in ['A', 'B', 'C', 'D']:
            messagebox.showwarning("Resposta inválida", "Digite A, B, C ou D para responder.")
            return

        self.entry_resposta.delete(0, "end")
        self.atualizar_chat(resposta_usuario, "user")

        correta = (resposta_usuario == self.resposta_correta_atual)
        if correta:
            self.acertos += 1

        texto_correcao = f"Resposta correta: {self.resposta_correta_atual}\nExplicação: {self.explicacao_atual}"
        texto_feedback = f"{'Acertou!' if correta else 'Errou.'} {texto_correcao}"

        self.atualizar_chat(texto_feedback, "assistant")

        # Ler a explicação e a resposta correta automaticamente
        texto_para_voz = f"{'Acertou!' if correta else 'Errou.'} Resposta correta: {self.resposta_correta_atual}. Explicação: {self.explicacao_atual}."
        ler_texto(texto_para_voz)

        # Bloqueia novas respostas por 15 segundos para o TTS ler
        self.aguardando_proxima = True
        self.entry_resposta.configure(state="disabled")
        self.btn_enviar.configure(state="disabled")

        def permitir_proxima():
            self.perguntas_respondidas += 1
            aproveitamento = int((self.acertos / self.perguntas_respondidas) * 100)

            # Atualiza barra de progresso e label aproveitamento
            self.progress.set(self.perguntas_respondidas / 8)
            self.label_aproveitamento.configure(text=f"Você está com {aproveitamento}% de aproveitamento até agora")

            if self.perguntas_respondidas >= 8:
                self.finalizar_quiz()
            else:
                self.gerar_pergunta_async()

            # Libera o bloqueio para nova resposta
            self.aguardando_proxima = False
            self.entry_resposta.configure(state="normal")
            self.btn_enviar.configure(state="normal")

        # Chama liberar após 10s
        self.after(10000, permitir_proxima)

    def finalizar_quiz(self):
        texto_final = f"Quiz finalizado! Você acertou {self.acertos} de 8 perguntas. Aproveitamento: {int((self.acertos / 8)*100)}%."
        self.atualizar_chat(texto_final, "assistant")
        ler_texto(texto_final)
        self.config_states(iniciar=True, quiz_ativo=False)

    def sair(self):
        if messagebox.askyesno("Sair", "Deseja realmente sair?"):
            apagar_todos_jsons()
            self.destroy()

    def speech_to_text():
        # Inicializar o reconhecedor
        recognizer = sr.Recognizer()

        # Usar o microfone como fonte de áudio
        with sr.Microphone() as source:
            print("Por favor, fale algo...")
            try:
                # Capturar o áudio
                audio = recognizer.listen(source)
                # Reconhecer a fala usando a API Google Web Speech (Português de Portugal)
                text = recognizer.recognize_google(audio, language="pt-PT")
                print("Você disse: " + text)
                return text
            except sr.UnknownValueError:
                print("Desculpe, não consegui entender o que você disse.")
            except sr.RequestError as e:
                print(f"Erro ao se conectar ao serviço de reconhecimento de fala: {e}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()
