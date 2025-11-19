"""
Complete AI Assistant with Wake Word Detection
Features: Porcupine wake word, Groq LLM, system access, user memory
"""

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
from typing import Dict, Optional
import threading
import queue
import warnings
import sys

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
        # Keep only last 20 conversations
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
        self.audio_device_index = audio_device_index
        
        # Initialize Porcupine with custom or built-in keyword
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
        
        # Try to open audio stream with specified device
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
        
        # Speech recognition with device
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300  # Lower for better sensitivity
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
        # Build system prompt with context
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
        # Check for system info requests
        command_lower = command.lower()
        
        if any(word in command_lower for word in ["time", "clock"]):
            response = f"It's currently {self.system_info.get_time()}"
        elif any(word in command_lower for word in ["date", "day", "today"]):
            response = f"Today is {self.system_info.get_date()}"
        elif any(word in command_lower for word in ["battery", "charge"]):
            response = f"Your battery is at {self.system_info.get_battery()}"
        elif "stop" in command_lower or "exit" in command_lower or "quit" in command_lower:
            self.speak("Goodbye! Have a great day!")
            self.running = False
            return
        else:
            # Get AI response
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
        print("Tip: Speak clearly and wait for the beep!")
        print("Debug: Press Ctrl+C to exit")
        print("="*50 + "\n")
        
        # Audio level monitoring
        frame_count = 0
        
        try:
            while self.running:
                # Listen for wake word
                pcm = self.audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)
                
                # Show audio activity every 50 frames (about every second)
                frame_count += 1
                if frame_count % 50 == 0:
                    audio_level = max(abs(min(pcm)), abs(max(pcm)))
                    if audio_level > 500:  # Significant audio detected
                        print(f"🎤 Audio detected (level: {audio_level}) - Say 'JARVIS' clearly!")
                
                keyword_index = self.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    print("🔔 Wake word detected!")
                    self.speak("Yes?")
                    
                    # Listen for command
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