import pvporcupine
import pyaudio
import struct
import json
import os
from datetime import datetime
import platform
import psutil
from groq import Groq
import speech_recognition as sr
import pyttsx3
from typing import Dict, Optional, List, Tuple
import threading
import queue
import warnings
import sys
import webbrowser
import subprocess
import shutil
import urllib.parse
import re
import glob
import customtkinter as ctk
from fuzzywuzzy import process, fuzz
import pygame

# Suppress Warnings
warnings.filterwarnings('ignore')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# Redirect ALSA error messages (Linux specific)
try:
    from ctypes import *
    ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
    def py_error_handler(filename, line, function, err, fmt):
        pass
    c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
    asound = cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
except:
    pass

# ------------------- UNIVERSAL APP LAUNCHER -------------------

class UniversalLauncher:
    def __init__(self):
        self.os_name = platform.system().lower()
        self.linux_apps = {} 
        if "linux" in self.os_name:
            self._cache_linux_apps()

    def _cache_linux_apps(self):
        search_paths = [
            "/usr/share/applications/",
            "/usr/local/share/applications/",
            os.path.expanduser("~/.local/share/applications/"),
            "/var/lib/snapd/desktop/applications/",
            "/snap/bin/"
        ]
        
        desktop_files = []
        for path in search_paths:
            if os.path.exists(path):
                if path.endswith("bin/"):
                    for f in os.listdir(path):
                        self.linux_apps[f.lower()] = os.path.join(path, f)
                else:
                    desktop_files.extend(glob.glob(os.path.join(path, "*.desktop")))

        for file_path in desktop_files:
            try:
                with open(file_path, 'r', errors='ignore') as f:
                    content = f.read()
                    name_match = re.search(r"^Name=(.*)", content, re.MULTILINE)
                    exec_match = re.search(r"^Exec=(.*)", content, re.MULTILINE)
                    if name_match and exec_match:
                        name = name_match.group(1).strip()
                        cmd = exec_match.group(1).strip()
                        cmd = re.sub(r" %[a-zA-Z]", "", cmd)
                        self.linux_apps[name.lower()] = cmd
                        if "visual studio code" in name.lower():
                            self.linux_apps["vs code"] = cmd
                            self.linux_apps["code"] = cmd
            except: continue

    def open_app(self, app_name: str) -> Tuple[bool, str]:
        if "windows" in self.os_name: return self._open_windows(app_name)
        elif "darwin" in self.os_name: return self._open_mac(app_name)
        else: return self._open_linux(app_name)

    def _open_windows(self, app_name: str):
        try:
            from AppOpener import open as app_open
            app_open(app_name, match_closest=True, output=True)
            return True, f"Opening {app_name}"
        except: return False, "Windows AppOpener failed."

    def _open_mac(self, app_name: str):
        try:
            subprocess.run(["open", "-a", app_name], check=True)
            return True, f"Opening {app_name}"
        except: return False, f"Could not find app '{app_name}'"

    def _open_linux(self, app_name: str):
        name = app_name.lower().strip()
        cmd = self.linux_apps.get(name)
        if not cmd:
            best_match, score = process.extractOne(name, list(self.linux_apps.keys()))
            if score > 60: cmd = self.linux_apps[best_match]
            else: return False, f"Could not find '{app_name}' on Linux."

        try:
            env = os.environ.copy()
            for key in ['LD_LIBRARY_PATH', 'PYTHONPATH', 'PYTHONHOME']:
                if key in env: del env[key]
            subprocess.Popen(cmd, shell=True, env=env, 
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, f"Opening {name}"
        except Exception as e: return False, f"Error launching {name}: {e}"


# ------------------- MUSIC PLAYER (UPDATED) -------------------

class LocalMusicPlayer:
    def __init__(self):
        user_home = os.path.expanduser("~")
        self.search_dirs = [
            os.path.join(user_home, "Music"),
            os.path.join(user_home, "Downloads")
        ]
        try: pygame.mixer.init()
        except: pass
        self.current_song = None

    def find_and_play(self, song_name):
        supported_exts = ('.mp3', '.wav', '.ogg', '.m4a', '.flac')
        files = []
        
        # If user provides full path, use it directly
        if os.path.exists(song_name) and os.path.isfile(song_name):
            files.append((song_name, os.path.basename(song_name)))
        else:
            # Scan folders
            for search_path in self.search_dirs:
                if os.path.exists(search_path):
                    for root, _, filenames in os.walk(search_path):
                        for filename in filenames:
                            if filename.lower().endswith(supported_exts):
                                files.append((os.path.join(root, filename), filename))

        if not files: return False, "No music files found."

        # Fuzzy match
        filenames_only = [f[1] for f in files]
        best_match, score = process.extractOne(os.path.basename(song_name), filenames_only)

        if score < 50: return False, f"Couldn't find '{song_name}'."

        full_path = next(f[0] for f in files if f[1] == best_match)
        try:
            if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
            pygame.mixer.music.load(full_path)
            pygame.mixer.music.play()
            self.current_song = best_match
            return True, f"Playing {best_match}"
        except Exception as e: return False, f"Error: {e}"

    # --- NEW CONTROLS ---
    def pause(self):
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            return "Music paused."
        return "Nothing is playing."

    def resume(self):
        try:
            pygame.mixer.music.unpause()
            return "Resuming music."
        except: return "Cannot resume."

    def stop(self):
        pygame.mixer.music.stop()
        return "Music stopped."


class MediaController:
    def __init__(self):
        self.launcher = UniversalLauncher()
    
    def open_app(self, app_name: str):
        return self.launcher.open_app(app_name)
        
    def play_online(self, query: str, service: str = "youtube") -> Tuple[bool, str]:
        if service.lower() in ["youtube", "yt"]:
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            webbrowser.open(url)
            return True, f"Searching {query} on YouTube"
        elif service.lower() == "spotify":
            url = f"http://open.spotify.com/search/{urllib.parse.quote(query)}"
            webbrowser.open(url)
            return True, f"Searching {query} on Spotify"
        return False, "Service not supported"

class UserMemory:
    def __init__(self, memory_file: str = "user_memory.json"):
        self.memory_file = memory_file
        self.data = self.load_memory()
    def load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r') as f: return json.load(f)
            except: pass
        return {"user_profile": {}, "conversation_history": []}
    def save_memory(self):
        with open(self.memory_file, 'w') as f: json.dump(self.data, f, indent=2)
    def add_conversation(self, user_msg, assistant_msg):
        self.data["conversation_history"].append({
            "timestamp": datetime.now().isoformat(),
            "user": user_msg, "assistant": assistant_msg
        })
        self.data["conversation_history"] = self.data["conversation_history"][-20:]
        self.save_memory()
    def get_context(self):
        context = []
        if self.data["user_profile"]:
            context.append(f"User Profile: {self.data['user_profile']}")
        if self.data["conversation_history"]:
            context.append("\nRecent conversations:")
            for conv in self.data["conversation_history"][-3:]:
                context.append(f"User: {conv['user']}\nAssistant: {conv['assistant']}")
        return "\n".join(context)

class SystemInfo:
    @staticmethod
    def get_time(): return datetime.now().strftime("%I:%M %p")
    @staticmethod
    def get_date(): return datetime.now().strftime("%A, %B %d, %Y")
    @staticmethod
    def get_battery():
        try:
            battery = psutil.sensors_battery()
            return f"{battery.percent}%" if battery else "Unknown"
        except: return "Unknown"

# ------------------- GUI & MAIN -------------------

class JarvisGUI(ctk.CTk):
    def __init__(self, assistant_ref):
        super().__init__()
        self.assistant = assistant_ref
        self.geometry("400x500")
        self.title("Jarvis AI")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.attributes('-topmost', True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.lbl_title = ctk.CTkLabel(self, text="J A R V I S", font=("Roboto Medium", 20))
        self.lbl_title.grid(row=0, column=0, pady=(30, 10))
        self.status_indicator = ctk.CTkButton(self, text="●", width=180, height=180, corner_radius=90, fg_color="#2B2B2B", hover_color="#2B2B2B", font=("Arial", 80), state="disabled")
        self.status_indicator.grid(row=1, column=0, pady=20)
        self.status_label = ctk.CTkLabel(self, text="Initializing...", font=("Roboto", 16))
        self.status_label.grid(row=2, column=0, pady=(10, 40))
        self.after(1000, self.start_assistant)

    def update_status(self, text, color):
        try:
            self.status_label.configure(text=text)
            self.status_indicator.configure(fg_color=color)
        except: pass

    def start_assistant(self):
        self.update_status("Waiting...", "#2CC985") 
        thread = threading.Thread(target=self.assistant.run_with_gui, args=(self,), daemon=True)
        thread.start()

class VoiceAssistant:
    def __init__(self, groq_api_key: str, porcupine_access_key: str, 
                 keyword_path: Optional[str] = None, audio_device_index: Optional[int] = None):
        self.groq_client = Groq(api_key=groq_api_key)
        self.memory = UserMemory()
        self.system_info = SystemInfo()
        self.media = MediaController()
        self.local_music = LocalMusicPlayer()
        self.audio_device_index = audio_device_index
        self.porcupine = None
        self.pa = None
        self.audio_stream = None
        try:
            if keyword_path and os.path.exists(keyword_path):
                self.porcupine = pvporcupine.create(access_key=porcupine_access_key, keyword_paths=[keyword_path])
            else:
                self.porcupine = pvporcupine.create(access_key=porcupine_access_key, keywords=["jarvis"])
            self.pa = pyaudio.PyAudio()
            self.audio_stream = self.pa.open(rate=self.porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=self.porcupine.frame_length, input_device_index=audio_device_index)
        except: pass
        self.recognizer = sr.Recognizer()
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 175)
        self.running = False
        self.tts_queue = queue.Queue()
        self.gui_ref = None

    def speak(self, text: str):
        print(f"Assistant: {text}")
        if self.gui_ref: self.gui_ref.update_status(f"Speaking...", "#9b59b6")
        self.tts_queue.put(text)
    
    def tts_worker(self):
        while self.running:
            try:
                text = self.tts_queue.get(timeout=1)
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
                if self.gui_ref: self.gui_ref.update_status("Waiting...", "#2CC985")
            except: continue

    def listen_for_command(self) -> Optional[str]:
        if self.gui_ref: self.gui_ref.update_status("Listening...", "#e74c3c")
        if not self.audio_stream: return None
        with sr.Microphone(device_index=self.audio_device_index) as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                if self.gui_ref: self.gui_ref.update_status("Processing...", "#3498db")
                command = self.recognizer.recognize_google(audio)
                print(f"User: {command}")
                return command
            except: return None

    def get_ai_response(self, user_input: str) -> str:
        sys_prompt = f"Time: {self.system_info.get_time()} Date: {self.system_info.get_date()} Battery: {self.system_info.get_battery()} {self.memory.get_context()} You are Jarvis. Helpful, concise, friendly."
        try:
            response = self.groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_input}], max_tokens=300)
            return response.choices[0].message.content
        except Exception as e: return f"Error: {e}"

    def process_command(self, command: str):
        cmd_lower = command.lower()
        
        # --- 1. MUSIC CONTROLS (Prioritized) ---
        if "pause" in cmd_lower:
            self.speak(self.local_music.pause())
            return
        if "resume" in cmd_lower or "continue" in cmd_lower:
            self.speak(self.local_music.resume())
            return
        if "stop music" in cmd_lower or "stop playing" in cmd_lower:
            self.speak(self.local_music.stop())
            return

        # --- 2. PLAY / SEARCH MEDIA ---
        # Now accepts 'search' and 'find' as well as 'play'
        play_match = re.match(r"^(play|search|find) (the )?(?P<query>.+?)(?: (?:on|in) (?P<service>youtube|spotify|yt))?$", cmd_lower)
        if play_match:
            query = play_match.group("query").strip()
            service = (play_match.group("service") or "").strip()
            
            # If user explicitly says "search ... on youtube", we force online search
            if "search" in cmd_lower or "find" in cmd_lower or service:
                if not service: service = "youtube" # Default to YouTube if just "Search X"
                self.speak(f"Searching for {query} on {service}")
                self.media.play_online(query, service)
                return
            
            # If user says "play X", we check local first
            found_local, msg = self.local_music.find_and_play(query)
            if found_local:
                self.speak(msg)
            else:
                self.speak(f"Searching online for {query}")
                self.media.play_online(query, "youtube")
            return

        # --- 3. OPEN APPS ---
        app_match = re.match(r"^(open|start|launch) (the )?(?P<app>.+)$", cmd_lower)
        if app_match:
            app_name = app_match.group("app").strip()
            success, msg = self.media.open_app(app_name)
            self.speak(msg)
            return

        # --- 4. SYSTEM / AI ---
        if "time" in cmd_lower: self.speak(f"It's {self.system_info.get_time()}")
        elif "date" in cmd_lower: self.speak(f"Today is {self.system_info.get_date()}")
        elif "exit" in cmd_lower or "quit" in cmd_lower or "stop" == cmd_lower: # Strict "stop" check
            self.speak("Goodbye!")
            if self.gui_ref: self.gui_ref.quit()
            self.running = False
        else:
            response = self.get_ai_response(command)
            self.speak(response)
            self.memory.add_conversation(command, response)

    def run_with_gui(self, gui_app):
        self.gui_ref = gui_app
        self.running = True
        threading.Thread(target=self.tts_worker, daemon=True).start()
        self.speak("Systems online.")
        if not self.audio_stream:
            self.speak("Microphone unavailable. Please restart in Text Mode.")
            return
        try:
            while self.running:
                pcm = self.audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                keyword_index = self.porcupine.process(pcm)
                if keyword_index >= 0:
                    self.speak("Yes?")
                    command = self.listen_for_command()
                    if command: self.process_command(command)
                    else:
                        if self.gui_ref: self.gui_ref.update_status("Waiting...", "#2CC985")
        except KeyboardInterrupt: pass
        finally: self.cleanup()

    def run_text_mode(self):
        self.running = True
        threading.Thread(target=self.tts_worker, daemon=True).start()
        print("\n" + "="*50 + "\n⌨️  TEXT TESTING MODE ACTIVATED\n" + "="*50 + "\n")
        try:
            while self.running:
                command = input("You > ").strip()
                if not command: continue
                self.process_command(command)
        except KeyboardInterrupt: print("\nStopping...")
        finally: self.cleanup()

    def cleanup(self):
        if self.audio_stream: self.audio_stream.close()
        if self.pa: self.pa.terminate()
        if self.porcupine: self.porcupine.delete()
        self.running = False

def list_audio_devices():
    pa = pyaudio.PyAudio()
    print("AUDIO DEVICES:")
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0: print(f"[{i}] {info['name']}")
    pa.terminate()

def main():
    print("="*50 + "\nJARVIS AI ASSISTANT\n" + "="*50)
    import dotenv
    dotenv.load_dotenv()
    groq_key = os.environ.get("GROQ_API_KEY") or input("Groq API Key: ").strip()
    ppn_key = os.environ.get("PORCUPINE_ACCESS_KEY") or input("Porcupine Key: ").strip()
    
    print("\nSelect Mode:\n1. Voice Mode\n2. Text Mode")
    mode = input("\nChoice (1/2): ").strip()
    
    device_idx = None
    if mode == '1':
        list_audio_devices()
        try:
            idx = input("\nSelect audio device index (Enter for default): ")
            if idx: device_idx = int(idx)
        except: pass

    try:
        assistant = VoiceAssistant(groq_key, ppn_key, audio_device_index=device_idx)
        if mode == '2': assistant.run_text_mode()
        else:
            app = JarvisGUI(assistant)
            app.mainloop()
    except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    main()