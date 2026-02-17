import collections
import threading
import time
import queue
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from piper.voice import PiperVoice
from openwakeword import Model

root = Path(__file__).resolve().parent.parent
sys.path.append(str(root))

from utils.helper import clean_text_for_tts
from config.settings import WAKE_WORD, WW_THRESHOLD, SILENCE_THRESHOLD
from utils.helper import setup_logger

logger = setup_logger(__name__)


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
        self._oww = None

        self.spech_buffer = collections.deque(maxlen=2000)
        self.is_speaking = False
        self.stop_speaking_event = threading.Event()
        self.last_ww_call = None

        self.sample_rate = 16000
        self.chunk_size = 1280

    @property
    def stt_model(self):
        if self._stt_model is None:
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
            self._tts_voice = PiperVoice.load(self.tts_model_path)
        return self._tts_voice

    @property
    def wake_model(self):
        if self._oww is None:
            self._oww = Model(wakeword_models=[WAKE_WORD], inference_framework="onnx")
        return self._oww

    def wait_for_wake_word(self):

        audio_queue = queue.Queue()

        def audio_callback(indata, frames, time, status):
            audio_queue.put(bytes(indata))

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk_size,
            callback=audio_callback,
        ):
            while True:
                chunk_int16 = np.frombuffer(audio_queue.get(), dtype=np.int16)

                prediction = self.wake_model.predict(chunk_int16)

                if prediction[WAKE_WORD] > WW_THRESHOLD:
                    self.last_ww_call = datetime.now()

                    if self.is_speaking:
                        self.stop_speaking_event.set()
                        time.sleep(0.1)

                    return self._record_command()

    def listen(self):
        return self._record_command()

    def _record_command(self, silence_timeout=2, max_duration=15):
        """Records until silence, effectively stripping the wake word logic."""
        command_audio = []
        silent_chunks = 0
        silence_limit = int(silence_timeout * self.sample_rate / self.chunk_size)
        max_chunks = int(max_duration * self.sample_rate / self.chunk_size)
        hard_limit_chunks = max_chunks * 6

        is_user_speaking = False
        total_chunks = 0

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk_size,
        ) as stream:
            while True:
                chunk, _ = stream.read(self.chunk_size)
                chunk = chunk.flatten()
                self.spech_buffer.extend(chunk)
                total_chunks += 1

                if total_chunks > hard_limit_chunks:
                    logger.warning("Hard limit reached. Force stopping.")
                    break

                if total_chunks > max_chunks and not is_user_speaking:
                    logger.warning("Max waiting duration reached, stopping.")
                    command_audio = []
                    break

                chunk_float = chunk.astype(np.float32) / 32768.0
                rms = np.sqrt(np.mean(chunk_float**2))

                logger.info(f"User speech Detected (RMS: {rms:.4f})")
                if rms > SILENCE_THRESHOLD:
                    if not is_user_speaking:
                        command_audio.append(
                            np.array(self.spech_buffer, dtype=np.int16)
                        )
                        is_user_speaking = True

                    command_audio.append(chunk)
                    silent_chunks = 0

                elif is_user_speaking:
                    command_audio.append(chunk)
                    silent_chunks += 1
                    if silent_chunks > silence_limit:
                        break

        if not command_audio:
            return ""

        data = np.concatenate(command_audio)
        data = data.astype(np.float32) / 32768.0
        logger.info(data)
        segments, _ = self.stt_model.transcribe(
            data,
            beam_size=3,
            temperature=0,
            language="en",
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
        )

        text = " ".join(s.text for s in segments).strip()

        clean_text = clean_text_for_tts(text)

        return clean_text

    def speak(self, text):
        """Synthesizes text to audio and plays it."""
        if not text:
            return

        self.is_speaking = True
        self.stop_speaking_event.clear()

        stream = sd.OutputStream(
            samplerate=self.tts_voice.config.sample_rate, channels=1, dtype="int16"
        )
        stream.start()

        for audio_chunk in self.tts_voice.synthesize(text):
            if self.stop_speaking_event.is_set():
                break
            stream.write(audio_chunk.audio_int16_array)

        stream.stop()
        stream.close()
        self.is_speaking = False
