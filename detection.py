import pvporcupine
import pyaudio
import struct
import json
import os
from datetime import datetime
from pathlib import Path
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

# Suppress ALSA warnings
warnings.filterwarnings('ignore')
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# Redirect ALSA error messages
from ctypes import *
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(filename, line, function, err, fmt):
    pass
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
try:
    asound = cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
except:
    pass


def list_audio_devices():
    """List all available audio input devices"""
    pa = pyaudio.PyAudio()
    print("\n" + "="*50)
    print("AVAILABLE AUDIO INPUT DEVICES")
    print("="*50)
    
    devices = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            devices.append(info)
            print(f"[{i}] {info['name']}")
            print(f"    Channels: {info['maxInputChannels']}, Sample Rate: {int(info['defaultSampleRate'])} Hz")
    
    pa.terminate()
    return devices


def test_microphone(device_index=None):
    """Test microphone recording and playback"""
    print("\n" + "="*50)
    print("MICROPHONE TEST")
    print("="*50)
    print("Recording for 3 seconds...")
    
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone(device_index=device_index) as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Listening... Say something!")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)
            
            print("Recognizing...")
            text = recognizer.recognize_google(audio)
            print(f"✓ You said: '{text}'")
            return True
    except sr.WaitTimeoutError:
        print("✗ No audio detected. Check your microphone.")
        return False
    except sr.UnknownValueError:
        print("✓ Audio detected but couldn't understand speech")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

class BrowserDetector:
    """Detects installed browsers across platforms"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.installed_browsers = self._detect_browsers()
    
    def _detect_browsers(self) -> Dict[str, Dict]:
        """Detect all installed browsers with their paths and commands"""
        browsers = {}
        
        if self.system == "windows":
            browsers = self._detect_windows_browsers()
        elif self.system == "darwin":
            browsers = self._detect_mac_browsers()
        else:
            browsers = self._detect_linux_browsers()
        
        return browsers
    
    def _detect_windows_browsers(self) -> Dict[str, Dict]:
        """Detect browsers on Windows"""
        browsers = {}
        
        browser_paths = {
            "chrome": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ],
            "firefox": [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
                r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            ],
            "edge": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ],
            "brave": [
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            ],
            "opera": [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe"),
                r"C:\Program Files\Opera\opera.exe",
            ],
            "vivaldi": [
                os.path.expandvars(r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe"),
            ],
        }
        
        for browser_name, paths in browser_paths.items():
            for path in paths:
                if os.path.exists(path):
                    browsers[browser_name] = {
                        "path": path,
                        "command": path,
                        "name": browser_name.title()
                    }
                    break
        
        return browsers
    
    def _detect_mac_browsers(self) -> Dict[str, Dict]:
        """Detect browsers on macOS"""
        browsers = {}
        
        browser_apps = {
            "chrome": "Google Chrome",
            "firefox": "Firefox",
            "safari": "Safari",
            "brave": "Brave Browser",
            "opera": "Opera",
            "edge": "Microsoft Edge",
        }
        
        for key, app_name in browser_apps.items():
            app_path = f"/Applications/{app_name}.app"
            if os.path.exists(app_path):
                browsers[key] = {
                    "path": app_path,
                    "command": app_name,
                    "name": app_name
                }
        
        return browsers
    
    def _detect_linux_browsers(self) -> Dict[str, Dict]:
        """Detect browsers on Linux"""
        browsers = {}
        
        browser_commands = {
            "chrome": ["google-chrome", "google-chrome-stable", "chrome"],
            "firefox": ["firefox"],
            "brave": ["brave-browser", "brave"],
            "opera": ["opera"],
            "chromium": ["chromium", "chromium-browser"],
            "edge": ["microsoft-edge"],
            "vivaldi": ["vivaldi"],
        }
        
        for key, commands in browser_commands.items():
            for cmd in commands:
                if shutil.which(cmd):
                    browsers[key] = {
                        "path": shutil.which(cmd),
                        "command": cmd,
                        "name": key.title()
                    }
                    break
        
        return browsers
    
    def get_browser(self, browser_name: str) -> Optional[Dict]:
        """Get browser info by name (case insensitive)"""
        name_lower = browser_name.lower()
        
        # Direct match
        if name_lower in self.installed_browsers:
            return self.installed_browsers[name_lower]
        
        # Fuzzy match
        for key, info in self.installed_browsers.items():
            if name_lower in key or key in name_lower:
                return info
        
        return None
    
    def get_default_browser(self) -> Optional[Dict]:
        """Get the default system browser"""
        if self.installed_browsers:
            return list(self.installed_browsers.values())[0]
        return None
    
    def list_browsers(self) -> List[str]:
        """Get list of installed browser names"""
        return [info["name"] for info in self.installed_browsers.values()]
    
    def open_browser(self, browser_name: Optional[str] = None, url: str = "about:blank") -> Tuple[bool, str]:
        """
        Open a browser with optional URL
        Returns: (success: bool, message: str)
        """
        if not browser_name or browser_name.lower() in ["default", "browser"]:
            browser_info = self.get_default_browser()
            if not browser_info:
                available = self.list_browsers()
                if available:
                    msg = f"No default browser set, but these are installed: {', '.join(available)}"
                else:
                    msg = "No browsers found on this system"
                return False, msg
            browser_name = list(self.installed_browsers.keys())[0]
        
        browser_info = self.get_browser(browser_name)
        
        if not browser_info:
            available = self.list_browsers()
            if available:
                msg = f"{browser_name} is not installed. Available browsers: {', '.join(available)}"
            else:
                msg = f"{browser_name} is not installed and no other browsers were found"
            return False, msg
        
        try:
            if self.system == "windows":
                if url and url != "about:blank":
                    subprocess.Popen([browser_info["path"], url])
                else:
                    os.startfile(browser_info["path"])
                return True, f"Opened {browser_info['name']}"
            
            elif self.system == "darwin":
                cmd = ["open", "-a", browser_info["command"]]
                if url and url != "about:blank":
                    cmd.append(url)
                subprocess.Popen(cmd)
                return True, f"Opened {browser_info['name']}"
            
            else:  # Linux
                cmd = [browser_info["command"]]
                if url and url != "about:blank":
                    cmd.append(url)
                subprocess.Popen(cmd)
                return True, f"Opened {browser_info['name']}"
        
        except Exception as e:
            return False, f"Failed to open {browser_info['name']}: {str(e)}"

class YouTubeHandler:
    """Handles YouTube search and autoplay"""
    
    @staticmethod
    def search_and_play(query: str, browser_detector: BrowserDetector) -> Tuple[bool, str]:
        """
        Search YouTube and play the first result
        Returns: (success: bool, message: str)
        """
        search_query = urllib.parse.quote(query)
        play_url = f"https://www.youtube.com/results?search_query={search_query}"
        
        success, msg = browser_detector.open_browser(url=play_url)
        
        if success:
            return True, f"Playing '{query}' on YouTube"
        else:
            try:
                webbrowser.open(play_url)
                return True, f"Playing '{query}' on YouTube"
            except Exception as e:
                return False, f"Failed to open YouTube: {str(e)}"

class MediaController:
    """Manages media playback and application launching"""
    
    def __init__(self):
        self.browser_detector = BrowserDetector()
        self.youtube_handler = YouTubeHandler()
        detected = self.browser_detector.list_browsers()
        if detected:
            print(f"✓ Detected browsers: {', '.join(detected)}")
    
    def open_app(self, app_name: str) -> Tuple[bool, str]:
        """
        Open an application
        Returns: (success: bool, message: str)
        """
        if not app_name:
            return False, "No app name provided"
        
        name = app_name.strip().lower()
        system = platform.system().lower()
        
        # Handle browser requests
        if name in ["browser", "default browser", "web browser"]:
            return self.browser_detector.open_browser()
        
        # Check if it's a specific browser
        browser_names = ["chrome", "firefox", "safari", "edge", "brave", "opera", "vivaldi", "chromium"]
        if any(bn in name for bn in browser_names):
            for bn in browser_names:
                if bn in name:
                    return self.browser_detector.open_browser(bn)
        
        # Common app aliases
        alias_map = {
            "spotify": ["spotify", "Spotify"],
            "vlc": ["vlc", "VLC"],
            "calculator": ["calc", "calculator", "gnome-calculator"],
            "notepad": ["notepad"],
            "code": ["code", "Visual Studio Code"],
            "youtube": ["youtube"],
        }
        
        # Special case: YouTube
        if "youtube" in name:
            return self.browser_detector.open_browser(url="https://www.youtube.com")
        
        # Try to launch app
        candidates = alias_map.get(name, [app_name])
        
        for candidate in candidates:
            if os.path.exists(candidate):
                try:
                    if system == "windows":
                        os.startfile(candidate)
                        return True, f"Opened {app_name}"
                    else:
                        subprocess.Popen([candidate])
                        return True, f"Opened {app_name}"
                except Exception:
                    continue
            
            if shutil.which(candidate):
                try:
                    subprocess.Popen([candidate])
                    return True, f"Opened {app_name}"
                except Exception:
                    continue
            
            if system == "windows":
                try:
                    result = ctypes.windll.shell32.ShellExecuteW(None, "open", candidate, None, None, 1)
                    if int(result) > 32:
                        return True, f"Opened {app_name}"
                except Exception:
                    pass
            elif system == "darwin":
                try:
                    subprocess.Popen(["open", "-a", candidate])
                    return True, f"Opened {app_name}"
                except Exception:
                    pass
        
        return False, f"{app_name} is not installed on this system"
    
    def play_media(self, query: str, service: str = "youtube") -> Tuple[bool, str]:
        """
        Play media content
        Returns: (success: bool, message: str)
        """
        if service.lower() in ["youtube", "yt"]:
            return self.youtube_handler.search_and_play(query, self.browser_detector)
        elif service.lower() == "spotify":
            uri = f"spotify:search:{urllib.parse.quote(query)}"
            success, msg = self.open_app("spotify")
            if success:
                try:
                    if platform.system().lower() == "windows":
                        os.startfile(uri)
                    else:
                        subprocess.Popen(["xdg-open", uri])
                    return True, f"Playing '{query}' on Spotify"
                except:
                    pass
            
            url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
            return self.browser_detector.open_browser(url=url)
        
        return False, f"Service {service} not supported"


class UserMemory:
    """Manages user information and conversation history"""
    
    def __init__(self, memory_file: str = "user_memory.json"):
        self.memory_file = memory_file
        self.data = self.load_memory()
        
    def load_memory(self) -> Dict:
        """Load user memory from file"""
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                return json.load(f)
        return {
            "user_profile": {},
            "conversation_history": [],
            "preferences": {},
            "last_interaction": None
        }
    
    def save_memory(self):
        """Save user memory to file"""
        with open(self.memory_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def update_profile(self, key: str, value: str):
        """Update user profile information"""
        self.data["user_profile"][key] = value
        self.save_memory()
    
    def add_conversation(self, user_msg: str, assistant_msg: str):
        """Add conversation to history (keep last 20)"""
        self.data["conversation_history"].append({
            "timestamp": datetime.now().isoformat(),
            "user": user_msg,
            "assistant": assistant_msg
        })
        self.data["conversation_history"] = self.data["conversation_history"][-20:]
        self.data["last_interaction"] = datetime.now().isoformat()
        self.save_memory()
    
    def get_profile(self) -> Dict:
        """Get user profile"""
        return self.data["user_profile"]
    
    def is_profile_complete(self) -> bool:
        """Check if basic profile is complete"""
        required_fields = ["name", "age", "gender"]
        return all(field in self.data["user_profile"] for field in required_fields)
    
    def get_context(self) -> str:
        """Get conversation context for AI"""
        context = []
        if self.data["user_profile"]:
            profile_str = ", ".join([f"{k}: {v}" for k, v in self.data["user_profile"].items()])
            context.append(f"User Profile: {profile_str}")
        
        if self.data["conversation_history"]:
            context.append("\nRecent conversations:")
            for conv in self.data["conversation_history"][-5:]:
                context.append(f"User: {conv['user']}\nAssistant: {conv['assistant']}")
        
        return "\n".join(context)


class SystemInfo:
    """Provides system information (cross-platform)"""
    
    @staticmethod
    def get_time() -> str:
        """Get current time"""
        return datetime.now().strftime("%I:%M %p")
    
    @staticmethod
    def get_date() -> str:
        """Get current date"""
        return datetime.now().strftime("%A, %B %d, %Y")
    
    @staticmethod
    def get_battery() -> Optional[str]:
        """Get battery percentage (if available)"""
        try:
            battery = psutil.sensors_battery()
            if battery:
                percent = battery.percent
                plugged = "plugged in" if battery.power_plugged else "on battery"
                return f"{percent}% ({plugged})"
            return "Battery information not available"
        except Exception as e:
            return f"Cannot access battery: {str(e)}"
    
    @staticmethod
    def get_system_info() -> str:
        """Get system information"""
        return f"{platform.system()} {platform.release()}"


class VoiceAssistant:
    """Main AI Assistant with wake word detection"""
    
    def __init__(self, groq_api_key: str, porcupine_access_key: str, 
                 keyword_path: Optional[str] = None, audio_device_index: Optional[int] = None):
        # Initialize components
        self.groq_client = Groq(api_key=groq_api_key)
        self.memory = UserMemory()
        self.system_info = SystemInfo()
        self.media = MediaController()
        self.audio_device_index = audio_device_index
        
        # Initialize Porcupine
        if keyword_path and os.path.exists(keyword_path):
            print(f"✓ Using custom wake word model: {keyword_path}")
            self.porcupine = pvporcupine.create(
                access_key=porcupine_access_key,
                keyword_paths=[keyword_path]
            )
        else:
            print("✓ Using built-in wake word: 'Jarvis'")
            self.porcupine = pvporcupine.create(
                access_key=porcupine_access_key,
                keywords=["jarvis"]
            )
        
        # Audio setup
        self.pa = pyaudio.PyAudio()
        
        try:
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length,
                input_device_index=audio_device_index
            )
            print(f"✓ Audio stream opened successfully")
        except Exception as e:
            print(f"✗ Error opening audio stream: {e}")
            raise
        
        # Speech recognition
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        
        # Text-to-speech
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 175)
        
        # State
        self.running = False
        self.tts_queue = queue.Queue()
        
    def speak(self, text: str):
        """Convert text to speech"""
        print(f"Assistant: {text}")
        self.tts_queue.put(text)
    
    def tts_worker(self):
        """Background worker for text-to-speech"""
        while self.running:
            try:
                text = self.tts_queue.get(timeout=1)
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS Error: {e}")
    
    def listen_for_command(self) -> Optional[str]:
        """Listen for voice command after wake word"""
        with sr.Microphone(device_index=self.audio_device_index) as source:
            print("🎤 Listening for command...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                command = self.recognizer.recognize_google(audio)
                print(f"User: {command}")
                return command
            except sr.WaitTimeoutError:
                self.speak("I didn't hear anything. Try again.")
                return None
            except sr.UnknownValueError:
                self.speak("Sorry, I didn't understand that.")
                return None
            except Exception as e:
                print(f"Error: {e}")
                return None
    
    def get_ai_response(self, user_input: str) -> str:
        """Get response from Groq LLM"""
        system_prompt = f"""You are a helpful AI assistant named Jarvis. You have access to system information and maintain memory of conversations with users.

Current System Info:
- Time: {self.system_info.get_time()}
- Date: {self.system_info.get_date()}
- Battery: {self.system_info.get_battery()}
- System: {self.system_info.get_system_info()}

{self.memory.get_context()}

Be conversational, friendly, and helpful. Keep responses concise (2-3 sentences unless more detail is needed)."""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"
    
    def setup_user_profile(self):
        """Initial setup to collect user information"""
        print("\n" + "="*50)
        print("FIRST TIME SETUP")
        print("="*50)
        print("Hello! I'm Jarvis, your AI assistant.")
        print("Let me get to know you better.\n")
        
        questions = [
            ("name", "What's your name?"),
            ("age", "How old are you?"),
            ("gender", "What's your gender? (male/female/other)")
        ]
        
        for key, question in questions:
            if key not in self.memory.get_profile():
                answer = input(f"{question} ").strip()
                if answer:
                    self.memory.update_profile(key, answer)
                    print(f"✓ Got it!\n")
        
        profile = self.memory.get_profile()
        self.speak(f"Nice to meet you, {profile.get('name')}! I'm ready to assist you. Just say your wake word to activate me.")
    
    def process_command(self, command: str):
        """Process user command"""
        import re
        
        command_lower = command.lower()
        
        # BROWSER COMMANDS
        if re.match(r"^open (the )?(default |web )?browser$", command_lower):
            success, msg = self.media.browser_detector.open_browser()
            self.speak(msg)
            self.memory.add_conversation(command, msg)
            return
        
        browser_match = re.match(r"^open (the )?(google )?(?P<browser>chrome|firefox|safari|edge|brave|opera|vivaldi|chromium)$", command_lower)
        if browser_match:
            browser_name = browser_match.group("browser")
            success, msg = self.media.browser_detector.open_browser(browser_name)
            self.speak(msg)
            self.memory.add_conversation(command, msg)
            return
        
        # GENERAL APP OPENING
        app_match = re.match(r"^(open|start|launch) (the )?(?P<app>.+)$", command_lower)
        if app_match:
            app_name = app_match.group("app").strip()
            success, msg = self.media.open_app(app_name)
            self.speak(msg)
            self.memory.add_conversation(command, msg)
            return
        
        # PLAY COMMANDS
        play_match = re.match(r"^play (the )?(?P<query>.+?)(?: (?:on|in) (?P<service>youtube|spotify|yt))?$", command_lower)
        if play_match:
            query = play_match.group("query").strip()
            service = (play_match.group("service") or "youtube").strip()
            
            self.speak(f"Playing {query} on {service}")
            success, msg = self.media.play_media(query, service)
            
            if not success:
                self.speak(msg)
            
            self.memory.add_conversation(command, msg)
            return
        
        # SYSTEM INFO
        if any(word in command_lower for word in ["time", "clock"]):
            response = f"It's currently {self.system_info.get_time()}"
            self.speak(response)
            self.memory.add_conversation(command, response)
            return
            
        if any(word in command_lower for word in ["date", "day", "today"]):
            response = f"Today is {self.system_info.get_date()}"
            self.speak(response)
            self.memory.add_conversation(command, response)
            return
            
        if any(word in command_lower for word in ["battery", "charge"]):
            response = f"Your battery is at {self.system_info.get_battery()}"
            self.speak(response)
            self.memory.add_conversation(command, response)
            return
            
        if "stop" in command_lower or "exit" in command_lower or "quit" in command_lower:
            self.speak("Goodbye! Have a great day!")
            self.running = False
            return
        
        # AI RESPONSE
        response = self.get_ai_response(command)
        self.speak(response)
        self.memory.add_conversation(command, response)
    
    def run(self):
        """Main loop - listen for wake word"""
        self.running = True
        
        # Start TTS worker thread
        tts_thread = threading.Thread(target=self.tts_worker, daemon=True)
        tts_thread.start()
        
        # Setup user profile if needed
        if not self.memory.is_profile_complete():
            self.setup_user_profile()
        else:
            profile = self.memory.get_profile()
            self.speak(f"Welcome back, {profile.get('name')}! Say your wake word to activate me.")
        
        print("\n" + "="*50)
        print("🎧 LISTENING FOR WAKE WORD")
        print("="*50)
        print("Say your wake word followed by your command")
        print("Examples:")
        print("  'Jarvis, open chrome'")
        print("  'Jarvis, play despacito'")
        print("  'Jarvis, what's the time?'")
        print("Press Ctrl+C to exit")
        print("="*50 + "\n")
        
        frame_count = 0
        
        try:
            while self.running:
                pcm = self.audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                
                frame_count += 1
                if frame_count % 50 == 0:
                    audio_level = max(abs(min(pcm)), abs(max(pcm)))
                    if audio_level > 500:
                        print(f"🎤 Audio detected (level: {audio_level}) - Say wake word!")
                
                keyword_index = self.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    print("🔔 Wake word detected!")
                    self.speak("Yes?")
                    
                    command = self.listen_for_command()
                    if command:
                        self.process_command(command)
                    
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        if self.audio_stream:
            self.audio_stream.close()
        if self.pa:
            self.pa.terminate()
        if self.porcupine:
            self.porcupine.delete()
        self.running = False


def main():
    """Main entry point"""
    print("="*50)
    print("AI Voice Assistant with Wake Word Detection")
    print("="*50)
    import dotenv
    dotenv.load_dotenv()
    
    # Get API keys
    groq_api_key = os.environ.get("GROQ_API_KEY")
    porcupine_access_key = os.environ.get("PORCUPINE_ACCESS_KEY")
    
    if not groq_api_key:
        print("\nError: GROQ_API_KEY environment variable not set")
        print("Get your key from: https://console.groq.com/")
        groq_api_key = input("Enter your Groq API key: ").strip().strip('"').strip("'")
    
    if not porcupine_access_key:
        print("\nError: PORCUPINE_ACCESS_KEY environment variable not set")
        print("Get your key from: https://console.picovoice.ai/")
        porcupine_access_key = input("Enter your Porcupine access key: ").strip().strip('"').strip("'")
    
    # Check for custom keyword model
    keyword_path = None
    if os.path.exists("wake_word.ppn"):
        keyword_path = "wake_word.ppn"
    else:
        print("\nNo custom wake word model found (wake_word.ppn)")
        custom_path = input("Enter path to .ppn file (or press Enter to use built-in 'Jarvis'): ").strip()
        if custom_path and os.path.exists(custom_path):
            keyword_path = custom_path
    
    # List audio devices
    devices = list_audio_devices()
    
    # Select audio device
    audio_device_index = None
    if len(devices) > 1:
        choice = input("\nSelect audio device index (or press Enter for default): ").strip()
        if choice.isdigit() and int(choice) < len(devices):
            audio_device_index = int(choice)
            print(f"✓ Selected device: {devices[audio_device_index]['name']}")
    
    # Test microphone
    print("\n" + "="*50)
    test = input("Test microphone before starting? (y/n): ").strip().lower()
    if test == 'y':
        if not test_microphone(audio_device_index):
            retry = input("\nMicrophone test failed. Continue anyway? (y/n): ").strip().lower()
            if retry != 'y':
                print("Exiting...")
                return
    
    # Create and run assistant
    print("\n" + "="*50)
    print("Starting assistant...")
    print("="*50)
    
    try:
        assistant = VoiceAssistant(groq_api_key, porcupine_access_key, keyword_path, audio_device_index)
        assistant.run()
    except Exception as e:
        print(f"\n✗ Error starting assistant: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure your microphone is connected and working")
        print("2. Try selecting a different audio device")
        print("3. Check if another application is using the microphone")
        print("4. For custom wake words, ensure .ppn file is for your platform")


if __name__ == "__main__":
    main()