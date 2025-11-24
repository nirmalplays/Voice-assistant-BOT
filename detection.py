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
import subprocess
import shutil
import urllib.parse
import re
import glob
import math
import audioop # For calculating volume RMS
from fuzzywuzzy import process
import pygame
import random
import time
import requests

# Try imports
try:
    from youtubesearchpython import VideosSearch
    YOUTUBE_ENABLED = True
except: YOUTUBE_ENABLED = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except: SELENIUM_AVAILABLE = False

warnings.filterwarnings('ignore')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# ALSA Error Suppress
try:
    from ctypes import *
    ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
    def py_error_handler(filename, line, function, err, fmt): pass
    c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
    asound = cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
except: pass

# ------------------- HELPERS -------------------

class UniversalLauncher:
    def __init__(self):
        self.os_name = platform.system().lower()
        self.app_cache = {} 
        self._build_cache()
    def _build_cache(self):
        if "windows" in self.os_name: self._scan_windows()
        elif "linux" in self.os_name: self._scan_linux()
    def _scan_windows(self):
        paths = [os.path.join(os.environ.get("PROGRAMDATA","C:\\"), "Microsoft/Windows/Start Menu/Programs"),
                 os.path.join(os.environ.get("APPDATA","C:\\"), "Microsoft/Windows/Start Menu/Programs")]
        for p in paths:
            if os.path.exists(p):
                for r, _, fs in os.walk(p):
                    for f in fs:
                        if f.endswith(".lnk") or f.endswith(".url"):
                            self.app_cache[f.split('.')[0].lower()] = os.path.join(r, f)
    def _scan_linux(self):
        paths = ["/usr/share/applications/", "/snap/bin/"]
        for p in paths:
            if os.path.exists(p):
                for f in os.listdir(p):
                    if f.endswith(".desktop"):
                        try:
                            with open(os.path.join(p, f), 'r') as file:
                                c = file.read()
                                n = re.search(r"^Name=(.*)", c, re.M)
                                e = re.search(r"^Exec=(.*)", c, re.M)
                                if n and e: self.app_cache[n.group(1).lower()] = e.group(1).split()[0]
                        except: pass
                    else: self.app_cache[f.lower()] = os.path.join(p, f)
    def open(self, name):
        match = process.extractOne(name.lower(), list(self.app_cache.keys()))
        if match and match[1] > 60:
            cmd = self.app_cache[match[0]]
            try:
                if "windows" in self.os_name: os.startfile(cmd)
                else: subprocess.Popen(cmd, shell=True, stderr=subprocess.DEVNULL)
                return True, f"Opening {match[0]}"
            except: return False, "Error launching."
        return False, "App not found."
    def open_url(self, url):
        if "windows" in self.os_name: os.startfile(url)
        elif "darwin" in self.os_name: subprocess.Popen(["open", url])
        else: subprocess.Popen(["xdg-open", url], stderr=subprocess.DEVNULL)

class MusicPlayer:
    def __init__(self):
        self.data = {"songs":[], "playlists":{}}
        self.queue = []
        self.idx = 0
        self.is_playing = False
        pygame.mixer.init()
        self._scan()
    def _scan(self):
        for root, _, files in os.walk(os.path.expanduser("~")):
            if "/." in root: continue # skip hidden
            for f in files:
                if f.endswith(('.mp3','.wav','.flac')):
                    self.data["songs"].append({"path": os.path.join(root,f), "name":f})
    def play(self, query):
        match = process.extractOne(query, [s["name"] for s in self.data["songs"]])
        if match and match[1] > 60:
            song = next(s for s in self.data["songs"] if s["name"] == match[0])
            self.queue = [song["path"]]
            self.idx = 0
            self._start()
            return f"Playing {song['name']}"
        return False
    def _start(self):
        pygame.mixer.music.load(self.queue[self.idx])
        pygame.mixer.music.play()
        self.is_playing = True
    def pause(self): pygame.mixer.music.pause(); return "Paused"
    def resume(self): pygame.mixer.music.unpause(); return "Resumed"
    def stop(self): pygame.mixer.music.stop(); return "Stopped"
# ------------------- NEW WEB INTERFACE (SELENIUM) -------------------

class WebInterface:
    def __init__(self):
        self.driver = None
        self.running = False
        if SELENIUM_AVAILABLE:
            self._launch_ui()

    def _launch_ui(self):
        try:
            options = webdriver.ChromeOptions()

            # always load interface.html from the SAME FOLDER as detection.py
            script_dir = os.path.dirname(os.path.abspath(__file__))
            html_path = os.path.join(script_dir, "interface.html")

            # show in app-style window
            options.add_argument(f"--app=file:///{html_path.replace('\\', '/')}")
            options.add_argument("--start-maximized")
            options.add_experimental_option('excludeSwitches', ['enable-logging'])

            print("loading UI from:", html_path)  # debug print in terminal

            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
            self.running = True
        except Exception as e:
            print(f"UI Launch Error: {e}")

    def update_status(self, text, state="idle"):
        """Send status text to HTML (idle, listening, processing, speaking)"""
        if self.running:
            try:
                safe_text = text.replace("'", "").replace('"', "")
                self.driver.execute_script(
                    f"window.setStatus('{safe_text}', '{state}')"
                )
            except:
                self.running = False

    def update_amplitude(self, rms_value):
        """Send audio volume to HTML to pulse the sphere"""
        if self.running:
            try:
                # Normalize RMS (typically 0-30000) to 0.0-1.0
                normalized = min(rms_value / 5000, 1.0)
                self.driver.execute_script(
                    f"window.setAmplitude({normalized})"
                )
            except:
                pass

    def quit(self):
        if self.running:
            self.driver.quit()
            self.running = False


# ------------------- CORE ASSISTANT -------------------

class VoiceAssistant:
    def __init__(self, groq_key, ppn_key):
        self.groq = Groq(api_key=groq_key)
        self.porcupine = pvporcupine.create(access_key=ppn_key, keywords=["jarvis"])
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(rate=self.porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=self.porcupine.frame_length)
        self.rec = sr.Recognizer()
        self.tts = pyttsx3.init()
        self.tts.setProperty('rate', 175)
        
        self.launcher = UniversalLauncher()
        self.player = MusicPlayer()
        
        # Start the 3D UI
        self.ui = WebInterface()
        
        self.running = True

    def speak(self, text):
        print(f"AI: {text}")
        self.ui.update_status(text, "speaking")
        
        # Fake pulse animation during TTS (since we can't easily read TTS audio stream)
        # We just pulse randomly to simulate talking
        stop_pulse = False
        def pulse_anim():
            while not stop_pulse:
                self.ui.update_amplitude(random.randint(1000, 4000))
                time.sleep(0.1)
            self.ui.update_amplitude(0)

        t = threading.Thread(target=pulse_anim)
        t.start()
        
        self.tts.say(text)
        self.tts.runAndWait()
        
        stop_pulse = True
        t.join()
        self.ui.update_status("Waiting...", "idle")

    def process(self, cmd):
        cmd = cmd.lower()
        self.ui.update_status("Processing...", "processing")
        
        if "open" in cmd:
            app = cmd.replace("open", "").strip()
            ok, msg = self.launcher.open(app)
            self.speak(msg)
        elif "play" in cmd and ("youtube" in cmd or "online" in cmd):
            q = cmd.replace("play", "").replace("on youtube", "").strip()
            self.launcher.open_url(f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}")
            self.speak(f"Opened YouTube for {q}")
        elif "play" in cmd:
            q = cmd.replace("play", "").strip()
            msg = self.player.play(q)
            if msg: self.speak(msg)
            else: self.speak("Song not found.")
        elif "stop" in cmd or "exit" in cmd:
            self.speak("Goodbye.")
            self.running = False
        else:
            # AI Response
            try:
                resp = self.groq.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"user","content":cmd}],
                    max_tokens=100
                ).choices[0].message.content
                self.speak(resp)
            except Exception as e: self.speak("I had an error.")

    def run(self):
        self.speak("System Online.")
        try:
            while self.running:
                pcm = self.stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                
                # 1. Calculate Volume for UI
                rms = audioop.rms(pcm, 2)
                self.ui.update_amplitude(rms) # Pulse the UI based on ambient noise
                
                # 2. Wake Word
                pcm_unpacked = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                idx = self.porcupine.process(pcm_unpacked)
                
                if idx >= 0:
                    self.ui.update_status("Listening...", "listening")
                    # Play wake sound?
                    
                    # 3. Listen for Command
                    # We close the PyAudio stream momentarily to let SpeechRecognition take over
                    self.stream.close()
                    try:
                        with sr.Microphone() as source:
                            self.rec.adjust_for_ambient_noise(source, duration=0.5)
                            audio = self.rec.listen(source, timeout=5)
                            text = self.rec.recognize_google(audio)
                            self.process(text)
                    except:
                        self.ui.update_status("Didn't catch that.", "idle")
                    
                    # Reopen stream for Wake Word
                    self.stream = self.pa.open(rate=self.porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=self.porcupine.frame_length)

        except KeyboardInterrupt:
            pass
        finally:
            self.ui.quit()
            self.stream.close()
            self.porcupine.delete()

def main():
    import dotenv
    dotenv.load_dotenv()
    g_key = os.environ.get("GROQ_API_KEY") or input("Groq Key: ")
    p_key = os.environ.get("PORCUPINE_ACCESS_KEY") or input("Porcupine Key: ")
    
    bot = VoiceAssistant(g_key, p_key)
    bot.run()

if __name__ == "__main__":
    main()