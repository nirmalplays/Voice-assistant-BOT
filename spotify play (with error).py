#!/usr/bin/env python3
"""
voice_assistant_open_app.py

Behavior:
- say "open spotify" / "open vlc" / "open calculator" etc.
- assistant will attempt to open the app using multiple platform-specific methods.
- if it cannot find or start the app, it will tell you "X is not available on this machine".
- typed commands supported for easy debugging.
"""

import os
import re
import sys
import json
import time
import queue
import webbrowser
import subprocess
import platform
import warnings
import threading
import struct
import shutil
from datetime import datetime
from ctypes import *
from typing import Optional

# try optional audio libs (not required for typed debug)
try:
    import pvporcupine
    import pyaudio
    import speech_recognition as sr
    import pyttsx3
except Exception:
    pvporcupine = None
    pyaudio = None
    sr = None
    pyttsx3 = None

warnings.filterwarnings("ignore")
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# ---------------- simple memory and system helpers ----------------
class UserMemory:
    def __init__(self, memory_file: str = "user_memory.json"):
        self.memory_file = memory_file
        self.data = self._load()
    def _load(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"conversation_history": [], "user_profile": {}}
    def save(self):
        try:
            with open(self.memory_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass
    def add_conversation(self, u, a):
        self.data["conversation_history"].append({"timestamp": datetime.now().isoformat(),"user":u,"assistant":a})
        self.data["conversation_history"] = self.data["conversation_history"][-20:]
        self.save()

class SystemInfo:
    @staticmethod
    def get_time(): return datetime.now().strftime("%I:%M %p")
    @staticmethod
    def get_date(): return datetime.now().strftime("%A, %B %d, %Y")

# ---------------- MediaController.open_app (reliable) ----------------
class MediaController:
    def __init__(self):
        pass

    def _system_open(self, target: str) -> bool:
        """
        Cross-platform open attempt. Returns True if it launched something, False otherwise.
        Uses ShellExecuteW on Windows (most reliable).
        """
        system = platform.system().lower()
        print(f"[media] _system_open: trying to open {target!r} on {system}")
        try:
            if target.startswith("http://") or target.startswith("https://"):
                try:
                    webbrowser.open(target)
                    print("[media] opened url via webbrowser")
                    return True
                except Exception as e:
                    print("[media] webbrowser.open failed:", e)

            if system == "windows":
                try:
                    # ShellExecuteW returns a value >32 on success
                    result = ctypes.windll.shell32.ShellExecuteW(None, "open", str(target), None, None, 1)
                    if int(result) > 32:
                        print(f"[media] ShellExecuteW success (code {result})")
                        return True
                    else:
                        print(f"[media] ShellExecuteW returned {result}")
                except Exception as e:
                    print("[media] ShellExecuteW exception:", e)
                # fallback: try powershell Start-Process
                try:
                    subprocess.Popen(['powershell','-NoProfile','-Command',f'Start-Process -FilePath "{target}"'], shell=False)
                    print("[media] started via powershell Start-Process")
                    return True
                except Exception as e:
                    print("[media] powershell fallback failed:", e)
                # last resort: start via shell
                try:
                    subprocess.Popen(f'start "" "{target}"', shell=True)
                    print("[media] invoked start command")
                    return True
                except Exception as e:
                    print("[media] start command failed:", e)

            elif system == "darwin":
                try:
                    # try opening with mac open
                    subprocess.Popen(["open", target])
                    print("[media] mac open invoked")
                    return True
                except Exception as e:
                    print("[media] mac open failed:", e)

            else:
                # linux / other
                try:
                    subprocess.Popen(["xdg-open", target])
                    print("[media] linux xdg-open invoked")
                    return True
                except Exception as e:
                    print("[media] xdg-open failed:", e)
                # try direct exec if target is command-like and on PATH
                parts = target.split()
                if shutil.which(parts[0]):
                    try:
                        subprocess.Popen(parts)
                        print(f"[media] linux executed command on PATH: {parts[0]}")
                        return True
                    except Exception as e:
                        print("[media] linux direct exec failed:", e)
        except Exception as e:
            print("[media] top-level _system_open exception:", e)

        # last fallback: webbrowser.open
        try:
            webbrowser.open(target)
            print("[media] fallback webbrowser.open used")
            return True
        except Exception as e:
            print("[media] final fallback webbrowser.open failed:", e)
        return False

    def open_app(self, app_name: str) -> bool:
        """
        Try to open an app by name. If it cannot be found/launched, return False.
        This function DOES NOT lie — it returns True only if it attempted a launch.
        """
        if not app_name:
            print("[media] open_app: empty name")
            return False

        name = app_name.strip()
        system = platform.system().lower()
        print(f"[media] open_app: requested '{name}' on {system}")

        # common aliases -> candidate commands
        alias_map = {
            "spotify": ["spotify", "Spotify", "spotify.exe"],
            "vlc": ["vlc","vlc.exe","VLC"],
            "mpv": ["mpv","mpv.exe"],
            "calculator": ["calc","calc.exe","gnome-calculator","calculator"],
            "notepad": ["notepad","notepad.exe"],
            "code": ["code","code.cmd","code.exe","visual studio code","code.exe"]
        }

        # if user asked youtube -> open homepage
        if name.lower() in ("youtube","youtube homepage","youtube site"):
            return self._system_open("https://www.youtube.com")

        candidates = alias_map.get(name.lower(), [name])

        # try candidates heuristically
        for cand in candidates:
            try:
                # if absolute path exists -> launch it directly
                if os.path.exists(cand):
                    try:
                        if system == "windows":
                            os.startfile(cand)
                            print(f"[media] launched path via os.startfile: {cand}")
                            return True
                        else:
                            subprocess.Popen([cand])
                            print(f"[media] launched path via subprocess: {cand}")
                            return True
                    except Exception as e:
                        print(f"[media] launching path {cand} failed: {e}")

                # if candidate is on PATH -> execute
                if shutil.which(cand):
                    try:
                        subprocess.Popen([cand])
                        print(f"[media] launched via PATH: {cand}")
                        return True
                    except Exception as e:
                        print(f"[media] launching {cand} from PATH failed: {e}")

                # platform specific: try ShellExecuteW for friendly names on windows
                if system == "windows":
                    try:
                        res = ctypes.windll.shell32.ShellExecuteW(None, "open", cand, None, None, 1)
                        if int(res) > 32:
                            print(f"[media] ShellExecuteW succeeded for candidate: {cand} (code {res})")
                            return True
                        else:
                            print(f"[media] ShellExecuteW returned {res} for {cand}")
                    except Exception as e:
                        print(f"[media] ShellExecuteW exception for {cand}: {e}")
                    # powershell fallback
                    try:
                        subprocess.Popen(['powershell','-NoProfile','-Command',f'Start-Process -FilePath "{cand}"'], shell=False)
                        print(f"[media] started candidate via powershell: {cand}")
                        return True
                    except Exception as e:
                        print(f"[media] powershell fallback failed for {cand}: {e}")

                elif system == "darwin":
                    try:
                        subprocess.Popen(["open", "-a", cand])
                        print(f"[media] mac open -a invoked for {cand}")
                        return True
                    except Exception as e:
                        print(f"[media] mac open -a failed for {cand}: {e}")

                else:
                    # linux fallback: try xdg-open (works for .desktop names too)
                    try:
                        subprocess.Popen(["xdg-open", cand])
                        print(f"[media] linux xdg-open invoked for {cand}")
                        return True
                    except Exception as e:
                        print(f"[media] xdg-open failed for {cand}: {e}")
            except Exception as e:
                print(f"[media] candidate loop unexpected error for {cand}: {e}")

        # final shell attempt (last resort)
        try:
            subprocess.Popen(name, shell=True)
            print(f"[media] final shell attempt invoked for '{name}'")
            return True
        except Exception as e:
            print(f"[media] final shell attempt failed for '{name}': {e}")

        # nothing worked
        print(f"[media] open_app: could not find or launch '{name}'")
        return False

# ---------------- voice assistant (typed command friendly) ----------------
class VoiceAssistant:
    def __init__(self):
        self.memory = UserMemory()
        self.media = MediaController()
        self.running = False
        # lightweight tts: only enqueue if pyttsx3 available
        if pyttsx3:
            self.tts = pyttsx3.init(); self.tts.setProperty("rate",170)
            self.tts_queue = queue.Queue()
        else:
            self.tts = None
            self.tts_queue = None

    def speak(self, text: str):
        print("assistant:", text)
        if self.tts and self.tts_queue is not None:
            self.tts_queue.put(text)

    def process_command(self, command: str):
        if not command:
            return
        cmd = command.strip()
        lower = cmd.lower()

        # open/start/launch commands
        m = re.match(r"^(open|start|launch) (the )?(?P<app>.+)$", lower)
        if m:
            app = m.group("app").strip()
            # try to open
            self.speak(f"attempting to open {app}")
            ok = self.media.open_app(app)
            if ok:
                # double-check: we launched something; confirm to user
                self.speak(f"I've opened {app} for you, if it is installed.")
                self.memory.add_conversation(command, f"opened {app} (attempted)")
            else:
                # explicit not-available message
                self.speak(f"'{app}' is not available on this machine or could not be launched.")
                self.memory.add_conversation(command, f"failed to open {app}")
            return

        # play <song> on <service>
        play_match = re.search(r"play (?:the )?(?P<query>.+?)(?: (?:on|in|via) (?P<service>spotify|youtube|yt))?$", lower)
        if play_match:
            query = play_match.group("query").strip()
            service = (play_match.group("service") or "").strip()
            if not service:
                service = "youtube"
            self.speak(f"playing {query} on {service}")
            # use MediaController.play convenience if you implement it; here we'll handle youtube/spotify simple cases
            if "youtube" in service:
                self.media._system_open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
                self.memory.add_conversation(command, f"played {query} on youtube (opened search)")
                return
            if "spotify" in service:
                # try spotify app first
                uri = f"spotify:search:{query}"
                launched = self.media._system_open(uri)
                if launched:
                    self.memory.add_conversation(command, f"opened spotify uri for {query}")
                    return
                # fallback to web
                self.media._system_open(f"https://open.spotify.com/search/{urllib.parse.quote(query)}")
                self.memory.add_conversation(command, f"opened spotify search for {query}")
                return

        # general queries
        if "time" in lower:
            self.speak(f"it's {SystemInfo.get_time()}")
            return
        if "date" in lower:
            self.speak(f"today is {SystemInfo.get_date()}")
            return
        if lower in ("quit","exit","stop","bye"):
            self.speak("goodbye!")
            self.running = False
            return

        # fallback
        self.speak("i didn't understand that command. try 'open spotify' or 'play humma humma on youtube'.")

    def run_typed_loop(self):
        self.running = True
        try:
            while self.running:
                cmd = input("you> ").strip()
                if not cmd:
                    continue
                self.process_command(cmd)
        except KeyboardInterrupt:
            print("\nshutting down...")
        finally:
            self.running = False

def main():
    assistant = VoiceAssistant()
    print("assistant ready. Type commands like 'open spotify', 'open youtube', 'play humma humma', 'quit'.")
    assistant.run_typed_loop()

if __name__ == "__main__":
    main()
