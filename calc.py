import tkinter as tk
from tkinter import END, messagebox
from PIL import Image, ImageTk
import google.generativeai as genai
import pyttsx3
import speech_recognition as sr
import threading
import queue
import os

BG_COLOR = "#212121"
TEXT_COLOR = "#a6a6a6"
HEADER_BG = "black"
BTN_BG = "#ffffff"
FONT_HEADER = ("Arial", 31)
FONT_SUBHEADER = ("Arial", 10)
FONT_TEXT = ("Arial", 14)
FONT_INPUT = ("Arial", 12)


ASSETS_DIR = "assets"
os.makedirs(ASSETS_DIR, exist_ok=True)


GOOGLE_API_KEY = "" #Enter API KEY
genai.configure(api_key=GOOGLE_API_KEY)

generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

class CalcApp:
    def __init__(self, root):
        self.window = root
        self.setup_window()
        

        self.initialize_ai_model()
        self.initialize_tts_engine()
        self.initialize_speech_recognition()
        

        self.setup_header()
        self.setup_output()
        self.setup_input()
        self.setup_buttons()
        self.show_welcome_message()
        

        self.response_queue = queue.Queue()
        self.check_response_queue()

    def setup_window(self):
        """Configure main window settings."""
        self.window.geometry("800x600")
        self.window.title("CALC - Computational Assistance and Learning Companion")
        self.window.configure(bg=BG_COLOR)
        self.window.resizable(False, False)
        
        try:
            icon = Image.open(os.path.join(ASSETS_DIR, "icon.png"))
            icon = icon.resize((42, 42))
            self.window.iconphoto(True, ImageTk.PhotoImage(icon))
        except FileNotFoundError:
            print("Icon file not found. Using default icon.")

    def setup_header(self):
        """Setup header section."""
        self.canvas = tk.Canvas(self.window, bg='black')
        self.canvas.place(x=0, y=0, relwidth=1, relheight=0.11)
        self.header = tk.Label(self.window, text="CALC", font=FONT_HEADER, bg=HEADER_BG, fg="white")
        self.header.place(x=10, y=5)
        self.ver = tk.Label(self.window, text="Beta v1.0", font=FONT_SUBHEADER, bg=HEADER_BG, fg="white")
        self.ver.place(x=130, y=25)

    def setup_output(self):
        """Setup output box."""
        self.output_box = tk.Text(
            self.window, 
            width=70, 
            height=10, 
            bd=2, 
            relief="flat", 
            bg=BG_COLOR, 
            fg=TEXT_COLOR, 
            font=FONT_TEXT, 
            wrap="word"
        )
        self.output_box.place(relheight=0.6, relwidth=0.8, relx=0.1, rely=0.12)
        self.output_box.configure(state="disabled", cursor="arrow")
        self.output_box.tag_configure("user_input", foreground="blue")

    def setup_input(self):
        """Setup input box."""
        self.textbox = tk.Text(
            self.window, 
            fg=TEXT_COLOR,
            font=FONT_INPUT,
            bg="#454545", 
            height=3, 
            width=50, 
            bd=2, 
            relief="flat",
            wrap="word"
        )
        self.textbox.pack(side=tk.BOTTOM, pady=80, padx=10)

    def initialize_ai_model(self):
        """Setup Google Generative AI model."""
        try:
            self.model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config=generation_config,
                system_instruction=(
                    "You are an expert teacher teaching high-school level mathematics specifically algebra. "
                    "Your name is CALC and it stands for Computational Assistance and Learning Companion. "
                    "Strictly answer questions related to algebra topics if the question is not related to algebra tell them that it is not part of your function. Provide clear, educational explanations."
                    "Don't use * as bullet points you can use * in multiplication equations."
                    "Do not use $boxed$ when highlighting the answer"
                    "Do not store the history of the conversation. When the user access the app it will start a new conversation."
                )
            )
            self.chat_session = self.model.start_chat()
        except Exception as e:
            messagebox.showerror("AI Model Error", f"Failed to initialize AI model: {e}")
            self.model = None
            self.chat_session = None

    def initialize_tts_engine(self):
        """Initialize text-to-speech engine safely."""
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty("rate", 150)
            self.tts_engine.setProperty("volume", 1.0)
            self.tts_enabled = True
        except Exception as e:
            messagebox.showwarning("TTS Error", f"Text-to-speech unavailable: {e}")
            self.tts_enabled = False

    def initialize_speech_recognition(self):
        """Setup speech recognition components."""
        self.processing = False
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True

    def setup_buttons(self):
        """Setup interaction buttons with error handling."""
        try:
            self.voice_icon = tk.PhotoImage(file=os.path.join(ASSETS_DIR, "microphone.png"))
        except tk.TclError:
            self.voice_icon = None
            print("Microphone icon not found.")

        self.voice_button = tk.Button(
            self.window, 
            image=self.voice_icon, 
            bg=BG_COLOR, 
            padx=10, 
            pady=5, 
            borderwidth=0, 
            command=self.start_voice_input
        )
        self.voice_button.place(relx=0.820, rely=0.822, anchor="center")

        self.send_button = tk.Button(
            self.window, 
            text="Send", 
            font=FONT_INPUT, 
            command=self.handle_text_input, 
            fg="black",
            bg=BTN_BG, 

        )
        self.send_button.place(relx=0.88, rely=0.842, anchor="center")

        self.tts_toggle_button = tk.Button(
            self.window, 
            text="TTS: On", 
            font=FONT_INPUT, 
            command=self.toggle_tts, 
            fg="black",
            bg=BTN_BG, 

        )
        self.tts_toggle_button.place(relx=0.15, rely=0.842, anchor="center")

        self.listening_label = tk.Label(
            self.window, 
            text="Listening...", 
            font=("Arial", 14), 
            bg=BG_COLOR, 
            fg="red"
        )
        self.listening_label.place_forget()

    def handle_text_input(self):
        """Handle user text input."""
        user_input = self.textbox.get("1.0", "end").strip()
        self.textbox.delete("1.0", END)
        
        if user_input and not self.processing:
            self.append_output(user_input, sender="You")
            self.generate_response(user_input)
            

            if hasattr(self, 'greeting_text'):
                self.greeting_text.place_forget()
            if hasattr(self, 'audio_wave_label'):
                self.audio_wave_label.place_forget()

    def show_welcome_message(self):
        """Display welcome message."""
        try:
            self.audio_wave = tk.PhotoImage(file=os.path.join(ASSETS_DIR, "audiowave.png"))
            self.audio_wave_label = tk.Label(
                self.window, 
                image=self.audio_wave, 
                bg=BG_COLOR
            )
            self.audio_wave_label.place(relx=0.5, rely=0.4, anchor="center")
        except Exception:
            self.audio_wave_label = None

        self.greeting_text = tk.Label(
            self.window, 
            text="Hi, I'm CALC. Ask me about algebra!", 
            font=("Arial", 18), 
            bg=BG_COLOR, 
            fg=TEXT_COLOR
        )
        self.greeting_text.place(relx=0.5, rely=0.5, anchor="center")

    def append_output(self, text, sender="CALC"):
        """Add text to the output box."""
        self.output_box.configure(state="normal")
        if sender == "You":
            self.output_box.insert(END, f"{sender}: ", "user_input")
            self.output_box.insert(END, f"{text}\n")
        else:
            self.output_box.insert(END, f"{sender}: {text}\n")
        self.output_box.configure(state="disabled")
        self.output_box.see(END)

    def toggle_tts(self):
        """Toggle text-to-speech with comprehensive handling."""
        self.tts_enabled = not self.tts_enabled
        status = "On" if self.tts_enabled else "Off"
        

        try:
            self.tts_engine.stop()
        except Exception:
            pass

        self.tts_toggle_button.config(text=f"TTS: {status}")
        self.append_output(f"Text-to-speech is now {status}.", sender="CALC")

    def start_voice_input(self):
        """Safely start voice input."""
        if not self.processing:
            threading.Thread(target=self.process_voice_input, daemon=True).start()

    def process_voice_input(self):
        """Robust voice input processing."""
        if self.processing:
            return

        self.processing = True
        self.listening_label.place(relx=0.5, rely=0.6, anchor="center")
        
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                
                user_input = self.recognizer.recognize_google(audio).strip()
                if user_input:
                    self.append_output(user_input, sender="You")
                    self.generate_response(user_input)
                

                if hasattr(self, 'greeting_text'):
                    self.greeting_text.place_forget()
                if hasattr(self, 'audio_wave_label'):
                    self.audio_wave_label.place_forget()
                
        except sr.UnknownValueError:
            self.append_output("Sorry, I couldn't understand that.", sender="CALC")
        except sr.RequestError:
            self.append_output("Speech recognition service unavailable.", sender="CALC")
        except Exception as e:
            self.append_output(f"Voice input error: {e}", sender="CALC")
        finally:
            self.processing = False
            self.listening_label.place_forget()

    def generate_response(self, user_input):
        """Thread-safe response generation."""
        def ai_response_task():
            try:
                response = self.chat_session.send_message(user_input)
                self.response_queue.put(response.text)
            except Exception as e:
                self.response_queue.put(f"Error generating response: {e}")

        threading.Thread(target=ai_response_task, daemon=True).start()

    def check_response_queue(self):
        """Check response queue and process responses."""
        try:
            while not self.response_queue.empty():
                response_text = self.response_queue.get_nowait()
                self.append_output(response_text)
                self.speak(response_text)
        except queue.Empty:
            pass
        

        self.window.after(100, self.check_response_queue)

    def speak(self, text):
        """Robust text-to-speech with threading."""
        if self.tts_enabled:
            threading.Thread(target=self._tts_task, args=(text,), daemon=True).start()

    def _tts_task(self, text):
        """Perform TTS in a thread-safe manner."""
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception:
            pass

    def on_exit(self):
        """Graceful application exit."""
        try:
            self.tts_engine.stop()
        except:
            pass
        self.window.quit()

def main():
    root = tk.Tk()
    app = CalcApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_exit)
    root.mainloop()

if __name__ == "__main__":
    main()
