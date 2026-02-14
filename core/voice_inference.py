import os
import wave
import io
import numpy as np
import sounddevice as sd
from pathlib import Path
from faster_whisper import WhisperModel
from piper.voice import PiperVoice
import sys

root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))

from utils.helper import clean_text_for_tts


class VoiceInference:
    def __init__(
        self,
        tts_model_path="./models/tts/en_GB-cori-high.onnx",
        stt_model_path="./models/stt",
    ):

        self.tts_model_path = str(root / tts_model_path)
        self.stt_model_path = str(root / stt_model_path)

        self._stt_model = None
        self._tts_voice = None
        self.sample_rate = 16000

    @property
    def stt_model(self):
        if self._stt_model is None:
            print("Loading STT model...")
            self._stt_model = WhisperModel(
                "base.en",
                device="cpu",
                compute_type="int8",
                download_root=self.stt_model_path,
            )
        return self._stt_model

    @property
    def tts_voice(self):
        if self._tts_voice is None:
            print("Loading TTS model...")
            self._tts_voice = PiperVoice.load(self.tts_model_path)
        return self._tts_voice

    def listen(self, silence_threshold=0.01, silence_duration=1.2, chunk_size=1024):
        print("Listening...")

        recording = []
        silent_chunks = 0
        speaking_started = False

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=chunk_size,
        ) as stream:
            while True:
                chunk, _ = stream.read(chunk_size)
                chunk = chunk.flatten()

                rms = np.sqrt(np.mean(chunk**2))

                if rms > silence_threshold:
                    speaking_started = True
                    silent_chunks = 0
                    recording.append(chunk)

                elif speaking_started:
                    recording.append(chunk)
                    silent_chunks += 1

                    if silent_chunks > (
                        silence_duration * self.sample_rate / chunk_size
                    ):
                        break

        if not recording:
            return ""

        audio_data = np.concatenate(recording)
        audio_data = np.ascontiguousarray(audio_data)

        segments, _ = self.stt_model.transcribe(audio_data, beam_size=2)

        text = " ".join(seg.text for seg in segments).strip()
        text = clean_text_for_tts(text)
        return text

    def speak(self, text):
        """Synthesizes text to audio and plays it."""
        if not text:
            return

        stream = sd.OutputStream(
            samplerate=self.tts_voice.config.sample_rate, channels=1, dtype="int16"
        )
        stream.start()

        for audio_chunk in self.tts_voice.synthesize(text):
            stream.write(audio_chunk.audio_int16_array)

        stream.stop()
        stream.close()
