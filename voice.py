"""Optional voice input/output for Jarvis.

Requires the voice extras (see requirements-voice.txt). Degrades gracefully:
if the packages aren't installed, Jarvis runs in text mode.
"""


class VoiceIO:
    def __init__(self):
        import pyttsx3
        import speech_recognition as sr

        self._sr = sr
        self._recognizer = sr.Recognizer()
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", 180)

    def listen(self) -> str | None:
        """Listen on the default microphone and return transcribed text."""
        with self._sr.Microphone() as source:
            print("\033[36m(listening...)\033[0m")
            self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = self._recognizer.listen(source, phrase_time_limit=15)
        try:
            return self._recognizer.recognize_google(audio)
        except self._sr.UnknownValueError:
            return None
        except self._sr.RequestError as exc:
            print(f"(speech recognition unavailable: {exc})")
            return None

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        self._engine.say(text)
        self._engine.runAndWait()


def get_voice_io() -> "VoiceIO | None":
    """Return a VoiceIO if the voice dependencies are installed, else None."""
    try:
        return VoiceIO()
    except ImportError:
        print(
            "Voice mode needs extra packages — install them with:\n"
            "  pip install -r requirements-voice.txt"
        )
        return None
    except Exception as exc:
        print(f"Voice mode unavailable: {exc}")
        return None
