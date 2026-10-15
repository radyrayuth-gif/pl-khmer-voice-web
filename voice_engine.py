import sys
import os
import subprocess
import traceback

if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Suppress black console window popups when spawning external commands (like FFmpeg) on Windows
if sys.platform == 'win32':
    _original_popen_init = subprocess.Popen.__init__
    def _patched_popen_init(self, *args, **kwargs):
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs['creationflags'] |= subprocess.CREATE_NO_WINDOW
        _original_popen_init(self, *args, **kwargs)
    subprocess.Popen.__init__ = _patched_popen_init

import re
import asyncio
import threading
import edge_tts
from pydub import AudioSegment

try:
    import mutagen.mp3
except ImportError:
    mutagen = None


def get_file_duration_ms(file_path: str) -> int:
    """
    Ultra-lightweight duration reader in pure Python.
    Uses mutagen (reads MP3 header in ~0.5ms with 0% CPU, no external processes).
    Falls back to pydub AudioSegment only if mutagen fails.
    """
    if mutagen:
        try:
            mp3 = mutagen.mp3.MP3(file_path)
            if mp3 and mp3.info and mp3.info.length > 0:
                return int(mp3.info.length * 1000)
        except Exception:
            pass
    try:
        audio = AudioSegment.from_file(file_path)
        return len(audio)
    except Exception:
        return 0

# If running in a PyInstaller bundle, point pydub to the bundled FFmpeg and FFprobe binaries
if getattr(sys, 'frozen', False):
    bundle_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
    ffmpeg_bin = os.path.join(bundle_dir, "ffmpeg.exe")
    ffprobe_bin = os.path.join(bundle_dir, "ffprobe.exe")
    if os.path.exists(ffmpeg_bin):
        AudioSegment.converter = ffmpeg_bin
    if os.path.exists(ffprobe_bin):
        AudioSegment.ffprobe = ffprobe_bin


try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTableWidget, QTableWidgetItem, QTextEdit, QLineEdit, QPushButton,
        QLabel, QComboBox, QSlider, QProgressBar, QTabWidget, QFileDialog,
        QMessageBox, QSplitter, QHeaderView, QAbstractItemView, QMenu,
        QGroupBox, QFormLayout, QCheckBox, QStyledItemDelegate
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer, QSize
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
    from PyQt5.QtGui import QFont, QIcon, QColor, QBrush, QTextCharFormat
except ImportError:
    # Running in headless web mode or on cloud server without PyQt5
    class _MockQObject:
        def __init__(self, *args, **kwargs): pass
        def emit(self, *args, **kwargs): pass
    class _MockSignal:
        def __init__(self, *args, **kwargs): pass
        def emit(self, *args, **kwargs): pass
        def connect(self, *args, **kwargs): pass
    QThread = _MockQObject
    def pyqtSignal(*args, **kwargs):
        return _MockSignal()
    Qt = QUrl = QTimer = QSize = None
    QMediaPlayer = QMediaContent = None
    QFont = QIcon = QColor = QBrush = QTextCharFormat = None

# Default sample SRT text provided by user
DEFAULT_SRT_TEXT = """1
00:00:00,000 --> 00:00:02,000
[មនុស្សស្រី | សំឡេង Echo] រីករាយផង រីករាយផង

2
00:00:02,000 --> 00:00:04,000
[មនុស្សស្រី] អរគុណអ្នកទាំងអស់គ្នាដែលបានមកចូលរួមកម្មវិធីអបអរសាទរការប្រឡងជាប់របស់ យេយេ

3
00:00:04,000 --> 00:00:06,000
[Human ស្រី] តោះពួកយើងអបអរសាទរដល់ យេយេ ដែលប្រឡងបាន ប្រាំពីររយម្ភៃ ពិន្ទុ

4
00:00:06,000 --> 00:00:08,000
[មនុស្សស្រី] ក្លាយជាសិស្សពូកែទូទាំងខេត្តក្នុងការប្រឡងបាក់ឌុប

5
00:00:08,000 --> 00:00:10,000
[មនុស្សស្រី] ល្អណាស់

6
00:00:12,000 --> 00:00:15,000
[មនុស្សស្រី] យេយេ លោកអ៊ំជឿជាក់ថាអ្នកប្រាកដជាអាចចូលរៀននៅសាកលវិទ្យាល័យ ឈីងប៉ី បានដោយគ្មានបញ្ហាឡើយ

7
00:00:15,000 --> 00:00:16,000
[មនុស្សស្រី] មែនទេអ្នកទាំងអស់គ្នា

8
00:00:16,000 --> 00:00:17,000
[មនុស្សប្រុស] មែនហើយ

9
00:00:17,000 --> 00:00:19,000
[មនុស្សស្រី] អរគុណលោកអ៊ំ

10
00:00:19,000 --> 00:00:22,000
[មនុស្សស្រី] ការចូលរៀននៅ ឈីងប៉ី គឺជាបំណងប្រាថ្នារបស់ខ្ញុំតាំងពីតូចមកម្ល៉េះ

11
00:00:22,000 --> 00:00:24,000
[មនុស្សស្រី] ពេលនេះទីបំផុតអាចសម្រេចបានហើយ

12
00:00:24,000 --> 00:00:26,000
[មនុស្សស្រី] ល្អ

13
00:00:26,000 --> 00:00:27,000
[មនុស្សស្រី] ល្អណាស់

14
00:00:27,000 --> 00:00:30,000
[មនុស្សស្រី] ជាការពិតណាស់ ទាំងនេះគឺជាគុណស្រមោចរបស់ អ្នកម៉ាក់

15
00:00:34,000 --> 00:00:36,000
[士兵] ចាត់ទុកថាអ្នកនៅមានសតិសម្បជញ្ញៈខ្លះ

16
00:00:36,000 --> 00:00:37,000
[មនុស្សស្រី] ប៉ុន្មានឆ្នាំមកនេះ

17
00:00:37,000 --> 00:00:40,000
[មនុស្សប្រុស] បើសិនជាគ្មានខ្ញុំរវល់មើលថែទាំងមុខទាំងក្រោយទេនោះ

18
00:00:40,000 --> 00:00:42,000
[មនុស្សស្រី] ត្រឹមខួរក្បាលដូចជាអ្នកនេះ

19
00:00:42,000 --> 00:00:44,000
[Echo] នៅចង់ប្រឡងចូល ឈីងប៉ី ទៀតឬ

20
00:00:44,000 --> 00:00:46,000
[មនុស្សស្រី] ប្រឡងដប់ជាតិទៀតក៏ប្រឡងមិនជាប់ដែរ

21
00:00:47,000 --> 00:00:49,000
[មនុស្សស្រី] សំណាងហើយដែលខ្ញុំប្រឡងជាប់សាកលវិទ្យាល័យ ឈីងប៉ី

22
00:00:49,000 --> 00:00:51,000
[មនុស្សស្រី] បន្តិចទៀត

23
00:00:51,000 --> 00:00:53,000
[មនុស្សប្រុស] ខ្ញុំនឹងក្លាយជាសិស្សពូកែប្រចាំខេត្តហើយ

24
00:00:53,000 --> 00:00:54,000
[មនុស្សស្រី] ត្រឡប់មកវិញ

25
00:00:54,000 --> 00:00:55,000
[មនុស្សស្រី] ពិតជាច្រណែនអ្នកណាស់

26
00:00:55,000 --> 00:00:57,000
[មនុស្សស្រី] ដែលមានកូនស្រីល្អបែបនេះ

27
00:00:57,000 --> 00:00:58,000
[មនុស្សស្រី] យេយេ ផ្ទះរបស់អ្នក

28
00:00:58,000 --> 00:01:00,000
[មនុស្សប្រុស] ពិតជាពូកែខ្លាំងណាស់

29
00:01:00,000 --> 00:01:01,000
[មនុស្សស្រី] អូយ

30
00:01:01,000 --> 00:01:02,000
[មនុស្សប្រុស] ពូកែមានប្រយោជន៍អីទៅ

31
00:01:02,000 --> 00:01:04,000
[មនុស្សស្រី] ក្មេងស្រីម្នាក់នេះណា

32
00:01:04,000 --> 00:01:06,000
[មនុស្សស្រី] មិនអាចឱ្យមានអនាគតខ្លាំងពេកទេ

33
00:01:06,000 --> 00:01:07,000
[មនុស្សស្រី] ថ្ងៃក្រោយទៅ

34
00:01:07,000 --> 00:01:09,000
[មនុស្សស្រី] គ្មានបុរសណាហ៊ានរៀបការជាមួយនាងឡើយ

35
00:01:09,000 --> 00:01:10,000
[មនុស្សស្រី] រឿងសាកលវិទ្យាល័យ ឈីងប៉ី នេះ

36
00:01:10,000 --> 00:01:12,000
[មនុស្សស្រី] តើវាមានតម្លៃស្អីទៅ

37
00:01:12,000 --> 00:01:13,000
[Human ប្រុស] វាមិនស្មើនឹង

38
00:01:13,000 --> 00:01:14,000
[មនុស្សស្រី] រៀបការឱ្យបានឆាប់នោះទេ

39
00:01:14,000 --> 00:01:15,000
[មនុស្សប្រុស] នេះនែ

40
00:01:15,000 --> 00:01:17,000
[មនុស្សស្រី] ខ្ញុំបានជួយ យេយេ របស់ពួកយើង

41
00:01:17,000 --> 00:01:19,000
[មនុស្សស្រី] ធ្វើខ្លួនឱ្យក្លាយជាក្មេងស្រីដ៏ល្អម្នាក់ហើយ"""


def timestamp_to_ms(ts_str):
    """Converts HH:MM:SS,mmm or HH:MM:SS.mmm to milliseconds."""
    try:
        ts_str = ts_str.strip().replace(',', '.')
        parts = ts_str.split(':')
        if len(parts) != 3:
            return 0
        h = int(parts[0])
        m = int(parts[1])
        s_parts = parts[2].split('.')
        s = int(s_parts[0])
        ms = 0
        if len(s_parts) > 1:
            ms_str = s_parts[1]
            if len(ms_str) == 1:
                ms = int(ms_str) * 100
            elif len(ms_str) == 2:
                ms = int(ms_str) * 10
            elif len(ms_str) == 3:
                ms = int(ms_str)
            else:
                ms = int(ms_str[:3])
        return (h * 3600 + m * 60 + s) * 1000 + ms
    except Exception:
        return 0


async def save_with_retry(communicate_factory, file_path, worker=None, base_delay=0.6, current_index=0):
    attempt = 0
    while True:
        if worker and not worker.is_running:
            return False
            
        # Check pause state before starting save
        while worker and worker.is_paused:
            if not worker.is_running:
                return False
            await asyncio.sleep(0.5)
            
        try:
            # Instantiate fresh Communicate from factory to avoid stale WebSocket / consumed texts generators
            fresh_comm = communicate_factory()
            await fresh_comm.save(file_path)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return True
        except Exception as e:
            if worker and not worker.is_running:
                return False
            attempt += 1
            if worker:
                if hasattr(worker, 'progress_warning'):
                    worker.progress_warning.emit(current_index, f"កំហុសតភ្ជាប់ (ព្យាយាមឡើងវិញ លើកទី #{attempt}): {e}")
                else:
                    worker.progress_error.emit(current_index, f"កំហុសតភ្ជាប់ (ព្យាយាមឡើងវិញ លើកទី #{attempt}): {e}")
            
            # Wait with exponential backoff (max 10s delay)
            delay = min(10.0, base_delay * (1.5 ** (attempt - 1)))
            
            # Sleep in intervals to check for stop/pause frequently
            slept = 0.0
            while slept < delay:
                if worker and not worker.is_running:
                    return False
                while worker and worker.is_paused:
                    if not worker.is_running:
                        return False
                    await asyncio.sleep(0.5)
                await asyncio.sleep(0.2)
                slept += 0.2


def ms_to_timestamp(ms):
    """Converts milliseconds to HH:MM:SS,mmm format."""
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_voice_and_echo_from_text(text, default_voice="Global"):
    # Detect tag at the beginning of the text: e.g. [មនុស្សស្រី | សំឡេង Echo] or [មនុស្សប្រុស]
    match = re.match(r'^\[(.*?)\]', text)
    voice = default_voice
    echo = False
    
    if match:
        tag_content = match.group(1).strip()
        # Voice detection
        if "ស្រី" in tag_content or "Sreymom" in tag_content or "Female" in tag_content or "female" in tag_content:
            voice = "Sreymom"
        elif "ប្រុស" in tag_content or "Piseth" in tag_content or "Male" in tag_content or "male" in tag_content or "士兵" in tag_content:
            voice = "Piseth"
            
        # Echo detection
        if "Echo" in tag_content or "echo" in tag_content or "ECHO" in tag_content or "សំឡេង" in tag_content:
            echo = True
            
    return voice, echo


# Pre-sorted list of common Khmer reduplicated words / suffixes for intelligent Lekh Tho (ៗ) expansion
COMMON_KHMER_REDUPLICATED_WORDS = sorted([
    # Multi-syllable compounds
    'បន្តិចបន្តួច', 'តិចតួច', 'រាល់ថ្ងៃ', 'រាល់ខែ', 'រាល់ឆ្នាំ', 'រាល់ពេល', 'ញឹកញាប់', 'ជួនកាល', 'យូរយារ',
    'ស្រស់ស្អាត', 'ត្រជាក់ត្រជុំ', 'កក់ក្ដៅ', 'ស្ងាត់ជ្រងំ', 'កំប៉ិកកំប៉ុក', 'រញ៉េរញ៉ៃ', 'រប៉ាត់រប៉ាយ',
    'រដិបរដុប', 'រលោងស្រិល', 'ក្រអូបឈ្ងុយ', 'ផ្អែមល្ហែម', 'សប្បាយរីករាយ', 'កម្សត់កម្រ',

    # Taste & Senses
    'ឆ្ងាញ់', 'ផ្អែម', 'ជូរ', 'ចត់', 'ល្វីង', 'ប្រៃ', 'សាប', 'ហឹរ', 'ឈ្ងុយ', 'ស្អុយ',

    # Speed, Time & Frequency
    'លឿន', 'យឺត', 'រហ័ស', 'ឆាប់', 'យូរ', 'ញឹក', 'ញ៉យ', 'មុន', 'ក្រោយ', 'ភ្លាម',

    # Size, Shape & Dimensions
    'ធំ', 'តូច', 'វែង', 'ខ្លី', 'ខ្ពស់', 'ទាប', 'ធាត់', 'ស្គម', 'ស្គាំង', 'មូល', 'កោង', 'វៀច', 'ត្រង់', 'ស្មើ',

    # Quantity & Degree
    'ច្រើន', 'តិច', 'បន្តិច', 'ខ្លាំង', 'ខ្សោយ', 'ណាស់', 'ពេក', 'ក្រែល', 'ស្ទើរ',

    # Distance & Space
    'ជិត', 'ឆ្ងាយ', 'ក្បែរ', 'លើ', 'ក្រោម', 'ក្នុង', 'ក្រៅ', 'ដើម', 'ចុង', 'មុខ',

    # Quality & State
    'ល្អ', 'អាក្រក់', 'ស្អាត', 'ថ្មី', 'ចាស់', 'ស្រាល', 'ធ្ងន់', 'ងាយ', 'ស្រួល', 'ពិបាក',
    'ស្ងាត់', 'ស្ងប់', 'ភ្លឺ', 'ងងឹត', 'ក្ដៅ', 'ត្រជាក់', 'រឹង', 'ទន់', 'រលោង', 'គគ្រើម',
    'ពិត', 'ជាក់', 'ច្បាស់', 'ផ្ទាល់', 'ប្រាកដ', 'ប្លែក',

    # Feelings, Health & Emotion
    'សប្បាយ', 'រីករាយ', 'កើតទុក្ខ', 'កម្សត់', 'សោកសៅ', 'ឈឺ', 'ចុក', 'ផ្សា', 'រមាស់',
    'ហត់', 'នឿយ', 'ឃ្លាន', 'ស្រេក', 'ឆ្អែត', 'ស្រួលខ្លួន',
    'ខ្លាច', 'ភ័យ', 'ស្លន់', 'តក់ស្លុត', 'ញ័រ',

    # People & Relations
    'ក្មេង', 'ចាស់', 'ស្រី', 'ប្រុស', 'មនុស្ស', 'បង', 'ប្អូន', 'កូន', 'ម៉ែ', 'ឪ',

    # Actions that commonly reduplicate
    'សើច', 'យំ', 'ស្រែក', 'ដើរ', 'រត់', 'ហោះ', 'ហើរ', 'លោត', 'មើល', 'គិត', 'ស្តាប់',
    'និយាយ', 'ធ្វើ', 'ញ៉ាំ', 'ហូប', 'ផឹក', 'ដេក', 'ដួល', 'អង្គុយ', 'ឈរ',

    # Sound words & Laughs
    'ហា', 'ហាស', 'ហ៊ឺ', 'ហ៊ា', 'ហិ', 'ហុ', 'អ្ហា', 'អូ', 'វ៉ាវ', 'គ្រុក', 'ដុក', 'ភឹប',

    # Indefinites & Determiners
    'ផ្សេង', 'គ្រប់', 'ខ្លះ', 'ឯង', 'មួយ', 'ពីរ', 'បី', 'បួន', 'ប្រាំ', 'ម្តង',
    'អី', 'ណា', 'នោះ', 'នេះ', 'ហ្នឹង', 'ចុះ', 'ឡើង'
], key=len, reverse=True)


def expand_khmer_lekh_tho(text: str) -> str:
    """
    Intelligently expands the Khmer Lekh Tho repetition mark 'ៗ' (U+17D7)
    into full repeated spoken words for flawless and melodious TTS pronunciation.
    Correctly isolates ONLY the single preceding word/syllable instead of repeating the entire clause.
    """
    if not text or 'ៗ' not in text:
        return text

    khmer_char = r'[\u1780-\u17D3\u17D8-\u17DD\u17E0-\u17E9A-Za-z0-9]'

    def expand_token(m):
        prefix_boundary = m.group(1)
        token = m.group(2)

        # 1. Check if token ends with a known common reduplicated word
        for w in COMMON_KHMER_REDUPLICATED_WORDS:
            if token.endswith(w):
                stem = token[:-len(w)]
                return f"{prefix_boundary}{stem}{w} {w}"

        # 2. Resilient fallback for unknown words:
        # In Khmer, Lekh Tho 'ៗ' NEVER repeats an entire long phrase.
        # If token is longer than 6 characters, extract only the trailing 1-2 orthographic clusters.
        if len(token) > 6:
            clusters = re.findall(
                r'[\u1780-\u17A2](?:[\u17D2][\u1780-\u17A2]|[\u17B6-\u17C5]|[\u17C6-\u17D3])*',
                token,
            )
            if clusters:
                last_word = ''.join(clusters[-2:]) if len(clusters) >= 2 else clusters[-1]
                stem = token[:-len(last_word)]
                return f"{prefix_boundary}{stem}{last_word} {last_word}"

        return f"{prefix_boundary}{token} {token}"

    pattern = rf'(\s|^|[^\u1780-\u17D3\u17D8-\u17DD\u17E0-\u17E9A-Za-z0-9])({khmer_char}+)\s*ៗ'

    prev = None
    curr = text
    while prev != curr and 'ៗ' in curr:
        prev = curr
        curr = re.sub(pattern, expand_token, curr)
        if 'ៗ' in curr and prev == curr:
            curr = re.sub(rf'({khmer_char}+)\s*ៗ', r'\1 \1', curr)
            if prev == curr:
                curr = curr.replace('ៗ', '')
                break

    # Normalize multiple whitespace
    curr = re.sub(r'[ \t]+', ' ', curr).strip()
    return curr


def clean_tts_text(text: str) -> str:
    """
    Cleans raw subtitle text for Edge-TTS:
    1. Removes character/voice bracket tags like [មនុស្សស្រី | សំឡេង Echo]
    2. Auto-expands Khmer repetition mark 'ៗ' to natural repeated spoken words
    """
    # Remove leading brackets like [មនុស្សស្រី] or [មនុស្សស្រី | សំឡេង Echo]
    cleaned = re.sub(r'^\[[^\]]+\]\s*', '', text)
    # Auto-expand Khmer Lekh Tho (ៗ) for fluent spoken speech
    cleaned = expand_khmer_lekh_tho(cleaned)
    return cleaned


def trim_leading_trailing_silence(sound, silence_threshold=-40.0, chunk_size=10, margin_ms=20):
    """
    Trims silence from the beginning and end of generated Edge-TTS audio.
    This eliminates latency/delay, ensuring speech begins exactly on the subtitle timestamp.
    """
    try:
        from pydub.silence import detect_leading_silence
        trim_start = detect_leading_silence(sound, silence_threshold=silence_threshold, chunk_size=chunk_size)
        trim_end = detect_leading_silence(sound.reverse(), silence_threshold=silence_threshold, chunk_size=chunk_size)
        
        trim_start = max(0, trim_start - margin_ms)
        trim_end = max(0, trim_end - margin_ms)
        
        duration = len(sound)
        if trim_start + trim_end >= duration:
            return sound
        return sound[trim_start:duration - trim_end]
    except Exception:
        return sound


def apply_echo_effect(audio, delay_ms=180, decay=0.5, num_echos=3, echo_reduction_percent=70):
    # Reduce echo volume by 70% (30% remaining level = -10.46 dB gain adjustment)
    extra_attenuation_db = 10.46
    tail_length = delay_ms * num_echos
    extended_audio = audio + AudioSegment.silent(duration=tail_length, frame_rate=audio.frame_rate)
    
    combined = extended_audio
    for i in range(1, num_echos + 1):
        # Attenuation in dB: 6dB decay per bounce + 10.46dB for 70% reduced echo volume
        attenuation = i * 6 + extra_attenuation_db
        silence = AudioSegment.silent(duration=i * delay_ms, frame_rate=audio.frame_rate)
        echo_clip = silence + audio.apply_gain(-attenuation)
        combined = combined.overlay(echo_clip)
    return combined


class SubtitleSegment:
    def __init__(self, index, start_str, end_str, start_ms, end_ms, text, speed_str="Default", audio_path="", duration_ms=0, status="Ready", voice="Auto", echo="Auto"):
        self.index = index
        self.start_str = start_str
        self.end_str = end_str
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.text = text
        self.speed_str = speed_str # "Default", "Auto", or manual value e.g. "+10%"
        self.audio_path = audio_path
        self.duration_ms = duration_ms
        self.status = status
        self.voice = voice # "Auto", "Sreymom", "Piseth"
        self.echo = echo # "Auto", "Yes", "No"


class TTSWorker(QThread):
    progress_started = pyqtSignal(int)          # index of segment
    progress_finished = pyqtSignal(int, str, int, str) # index, file_path, duration_ms, rate_used
    progress_warning = pyqtSignal(int, str)     # index, warning message
    progress_error = pyqtSignal(int, str)       # index, error message
    finished = pyqtSignal(int, int)             # success count, total count
    all_finished = finished                     # Signal alias for backwards compatibility

    def __init__(self, segments_data, voice="km-KH-SreymomNeural", rate="+0%", pitch="+0Hz", output_dir=None, bitrate="320k"):
        super().__init__()
        normalized_data = []
        default_out_dir = output_dir or os.path.abspath(os.path.join(os.getcwd(), "audio_output"))
        for item in (segments_data or []):
            if isinstance(item, dict):
                idx = item.get("index", 0)
                text = item.get("text", "")
                target_ms = item.get("target_ms", 0)
                seg_voice = item.get("voice", voice or "Auto")
                seg_echo = "Yes" if item.get("echo") else "No"
                speed_override = item.get("speed_override", "Default")
                out_p = item.get("output_path", "")
                if out_p:
                    file_name = os.path.basename(out_p)
                    if not output_dir:
                        default_out_dir = os.path.dirname(out_p)
                else:
                    file_name = f"sub_{idx:03d}.mp3"
                normalized_data.append((idx, text, file_name, target_ms, speed_override, seg_voice, seg_echo))
            elif isinstance(item, (list, tuple)):
                normalized_data.append(tuple(item))
            else:
                normalized_data.append(item)

        self.segments_data = normalized_data
        self.voice = voice or "km-KH-SreymomNeural"
        self.rate = rate or "+0%"
        self.pitch = pitch or "+0Hz"
        self.output_dir = output_dir or default_out_dir
        self.bitrate = bitrate or "320k"
        self.is_running = True
        self.is_paused = False
        self.current_index = 0

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.generate_all())
            finally:
                loop.close()
        except Exception as e:
            try:
                with open("crash.log", "a", encoding="utf-8") as f:
                    f.write(f"TTSWorker exception: {e}\n{traceback.format_exc()}\n")
            except Exception:
                pass
            if self.is_running:
                try:
                    self.progress_error.emit(-1, str(e))
                    self.finished.emit(0, len(self.segments_data))
                except Exception:
                    pass

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    async def generate_single(self, i, idx, text, file_name, target_ms, speed_override, seg_voice, seg_echo, semaphore, seg_pitch=None):
        async with semaphore:
            if not self.is_running:
                return False
                
            # Check pause state before starting a segment
            while self.is_paused:
                if not self.is_running:
                    return False
                await asyncio.sleep(0.5)
                
            if not self.is_running:
                return False
            
            self.progress_started.emit(idx)
            file_path = os.path.join(self.output_dir, file_name)
            
            try:
                rate_to_use = self.rate
                is_auto = False
                pitch_to_use = seg_pitch if (seg_pitch and seg_pitch != "Default") else self.pitch
                
                # Check speed configurations
                if speed_override.startswith("Auto") or speed_override == "Auto":
                    is_auto = True
                elif speed_override != "Default":
                    rate_to_use = speed_override # Custom manual rate (e.g. +10%)

                # 1. Resolve Voice
                if seg_voice == "Auto":
                    detected_voice, _ = parse_voice_and_echo_from_text(text, default_voice="Global")
                    if detected_voice == "Global":
                        resolved_voice = self.voice
                    else:
                        resolved_voice = "km-KH-SreymomNeural" if detected_voice == "Sreymom" else "km-KH-PisethNeural"
                else:
                    resolved_voice = "km-KH-SreymomNeural" if seg_voice == "Sreymom" else "km-KH-PisethNeural"

                # 2. Resolve Echo
                if seg_echo == "Auto":
                    _, resolved_echo = parse_voice_and_echo_from_text(text)
                elif seg_echo == "Yes":
                    resolved_echo = True
                else:
                    resolved_echo = False

                # 3. Clean TTS text (strip brackets)
                clean_text = clean_tts_text(text)
                has_speakable_content = bool(re.search(r'[\u1780-\u17FFa-zA-Z0-9]', clean_text))
                export_params = ["-q:a", "0", "-ar", "48000"]
                export_bitrate = getattr(self, "bitrate", "320k") or "320k"

                # Fast Disk Cache: If segment already exists and is valid, load instantly!
                if os.path.exists(file_path) and os.path.getsize(file_path) > 1024:
                    duration_ms = get_file_duration_ms(file_path)
                    if duration_ms > 0:
                        self.progress_finished.emit(idx, file_path, duration_ms, rate_to_use)
                        return True

                if not has_speakable_content:
                    silence_dur = max(200, min(target_ms, 5000)) if target_ms > 0 else 500
                    silent_audio = AudioSegment.silent(duration=silence_dur)
                    await asyncio.to_thread(silent_audio.export, file_path, format="mp3", bitrate=export_bitrate, parameters=export_params)
                    self.progress_finished.emit(idx, file_path, silence_dur, rate_to_use)
                    return True

                duration_ms = 0

                # 4. Calibrated 1-Pass Speech Rate Calculation based on Khmer Edge-TTS phonetics:
                # Natural speaking rate for Piseth/Sreymom with punctuation pauses is ~9.5 chars/sec (+0%).
                # We target 90% of target_ms to guarantee natural breathing room and ensure duration <= target_ms.
                if is_auto and target_ms > 0:
                    char_count = len(clean_text)
                    safe_target_sec = max(0.4, (target_ms * 0.90) / 1000.0)
                    est_sec = char_count / 9.5
                    
                    # Parse base rate percentage from global settings (e.g. "+20%" -> 20)
                    base_rate_pct = 0
                    try:
                        m_rate = re.search(r'([+-]?\d+)', str(self.rate or ""))
                        if m_rate:
                            base_rate_pct = int(m_rate.group(1))
                    except Exception:
                        base_rate_pct = 0

                    if est_sec > safe_target_sec:
                        calc_pct = int(((est_sec / safe_target_sec) - 1.0) * 100)
                        final_pct = max(base_rate_pct, min(90, calc_pct))
                        rate_to_use = f"{final_pct:+d}%"
                    else:
                        rate_to_use = self.rate or "+0%"

                # Single-Pass Direct Cloud Generation (Eliminates redundant double network roundtrips!)
                comm_factory = lambda: edge_tts.Communicate(
                    text=clean_text,
                    voice=resolved_voice,
                    rate=rate_to_use,
                    pitch=pitch_to_use
                )
                success = await save_with_retry(comm_factory, file_path, worker=self, current_index=i)
                if not success:
                    raise Exception("សកម្មភាពត្រូវបានបោះបង់ ឬមានបញ្ហាក្នុងការរក្សាទុកសំឡេង")
                
                # Read duration directly in pure Python (0% CPU, no external ffmpeg process)
                if os.path.exists(file_path):
                    duration_ms = get_file_duration_ms(file_path)
                
                # Apply echo effect ONLY if requested (keeps original pristine MP3 for standard lines)
                if resolved_echo and os.path.exists(file_path):
                    try:
                        audio = await asyncio.to_thread(AudioSegment.from_file, file_path)
                        def apply_and_export(a, path):
                            echoed = apply_echo_effect(a)
                            echoed.export(path, format="mp3", bitrate=export_bitrate, parameters=export_params)
                        await asyncio.to_thread(apply_and_export, audio, file_path)
                        duration_ms = get_file_duration_ms(file_path)
                    except Exception as e:
                        print(f"Failed to apply echo to {file_path}: {e}")

                self.progress_finished.emit(idx, file_path, duration_ms, rate_to_use)
                return True
            except Exception as e:
                if self.is_running:
                    self.progress_error.emit(idx, str(e))
                return False

    async def generate_all(self):
        total_count = len(self.segments_data)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Optimal concurrency limit of 16 for maximum Edge-TTS speed without socket throttling
        sem = asyncio.Semaphore(16)
        
        # Pass 1: Generate all segments concurrently with micro-stagger
        tasks = []
        for i, item in enumerate(self.segments_data):
            idx, text, file_name, target_ms, speed_override, seg_voice, seg_echo = item[:7]
            seg_pitch = item[7] if len(item) > 7 else None
            if i > 0 and i % 5 == 0:
                await asyncio.sleep(0.01)
            task = asyncio.create_task(
                self.generate_single(i, idx, text, file_name, target_ms, speed_override, seg_voice, seg_echo, sem, seg_pitch)
            )
            tasks.append(task)
            
        await asyncio.gather(*tasks, return_exceptions=True)

        # Pass 2 & 3: Automatic Zero-Skip Retry on any failed/missing segments
        for retry_pass in range(1, 4):
            if not self.is_running:
                break
            missing_indices = []
            for i, item in enumerate(self.segments_data):
                file_name = item[2]
                fp = os.path.join(self.output_dir, file_name)
                if not os.path.exists(fp) or os.path.getsize(fp) == 0:
                    missing_indices.append(i)
            
            if not missing_indices:
                break
            
            await asyncio.sleep(0.5)
            retry_sem = asyncio.Semaphore(8)
            retry_tasks = []
            for i in missing_indices:
                item = self.segments_data[i]
                idx, text, file_name, target_ms, speed_override, seg_voice, seg_echo = item[:7]
                seg_pitch = item[7] if len(item) > 7 else None
                t = asyncio.create_task(
                    self.generate_single(i, idx, text, file_name, target_ms, speed_override, seg_voice, seg_echo, retry_sem, seg_pitch)
                )
                retry_tasks.append(t)
            await asyncio.gather(*retry_tasks, return_exceptions=True)

        success_count = sum(
            1 for item in self.segments_data
            if os.path.exists(os.path.join(self.output_dir, item[2])) and os.path.getsize(os.path.join(self.output_dir, item[2])) > 0
        )
        self.finished.emit(success_count, total_count)

    def stop(self):
        self.is_running = False


class StreamingTTSWorker(TTSWorker):
    """
    Real-time Continuous Streaming TTS Worker.
    Consumes newly translated subtitle rows from an asynchronous queue in real-time.
    Enables instant Live Dubbing as each translation batch arrives without waiting.
    """
    def __init__(self, voice="km-KH-SreymomNeural", rate="+0%", pitch="+0Hz", output_dir=None, total_expected=0, bitrate="320k"):
        super().__init__(
            segments_data=[],
            voice=voice,
            rate=rate,
            pitch=pitch,
            output_dir=output_dir,
            bitrate=bitrate
        )
        self.total_expected = total_expected
        self._async_queue = None
        self._loop = None
        self._pending_before_loop = []
        self._pending_lock = threading.Lock()
        self._all_items_submitted = False
        self._seen_sub_indices = set()

    def add_segment(self, row_idx, sub_index, text, file_name, target_ms, speed_override, seg_voice, seg_echo, seg_pitch=None):
        if not self.is_running:
            return
        item = (row_idx, sub_index, text, file_name, target_ms, speed_override, seg_voice, seg_echo, seg_pitch)
        with self._pending_lock:
            if sub_index in self._seen_sub_indices:
                fp = os.path.join(self.output_dir, file_name)
                if os.path.exists(fp) and os.path.getsize(fp) > 1024:
                    return
            self._seen_sub_indices.add(sub_index)
            self.segments_data.append(item)
            if self._loop and self._loop.is_running() and self._async_queue:
                self._loop.call_soon_threadsafe(self._async_queue.put_nowait, item)
            else:
                self._pending_before_loop.append(item)

    def mark_finished_adding(self, total_expected=None):
        if total_expected is not None:
            self.total_expected = total_expected
        self._all_items_submitted = True
        if self._loop and self._loop.is_running() and self._async_queue:
            self._loop.call_soon_threadsafe(self._async_queue.put_nowait, None)

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._process_stream())
        finally:
            self._loop.close()

    async def _process_stream(self):
        os.makedirs(self.output_dir, exist_ok=True)
        self._async_queue = asyncio.Queue()

        # Push items received before the async loop started
        with self._pending_lock:
            for item in self._pending_before_loop:
                self._async_queue.put_nowait(item)
            self._pending_before_loop.clear()
            if self._all_items_submitted:
                self._async_queue.put_nowait(None)

        sem = asyncio.Semaphore(20)

        async def worker_coro():
            while self.is_running:
                item = await self._async_queue.get()
                if item is None:
                    # Put sentinel back for other consumer workers
                    await self._async_queue.put(None)
                    self._async_queue.task_done()
                    break
                row_idx, idx, text, file_name, target_ms, speed_override, seg_voice, seg_echo = item[:8]
                seg_pitch = item[8] if len(item) > 8 else None
                try:
                    await self.generate_single(row_idx, idx, text, file_name, target_ms, speed_override, seg_voice, seg_echo, sem, seg_pitch=seg_pitch)
                except Exception as e:
                    print(f"Streaming TTS error for row {row_idx}: {e}")
                finally:
                    self._async_queue.task_done()

        # Launch 20 concurrent consumer workers
        consumers = [asyncio.create_task(worker_coro()) for _ in range(20)]
        await asyncio.gather(*consumers, return_exceptions=True)

        # Multi-pass Zero-Skip Retry on any missing or zero-byte files
        for retry_pass in range(1, 4):
            if not self.is_running:
                break
            with self._pending_lock:
                current_items = list(self.segments_data)

            missing_items = []
            for item in current_items:
                row_idx, idx, text, file_name, target_ms, speed_override, seg_voice, seg_echo = item[:8]
                fp = os.path.join(self.output_dir, file_name)
                if not os.path.exists(fp) or os.path.getsize(fp) == 0:
                    missing_items.append(item)

            if not missing_items:
                break

            await asyncio.sleep(0.5)
            retry_sem = asyncio.Semaphore(12)
            retry_tasks = [
                asyncio.create_task(
                    self.generate_single(it[0], it[1], it[2], it[3], it[4], it[5], it[6], it[7], retry_sem, seg_pitch=it[8] if len(it) > 8 else None)
                )
                for it in missing_items
            ]
            await asyncio.gather(*retry_tasks, return_exceptions=True)

        with self._pending_lock:
            success_count = sum(
                1 for item in self.segments_data
                if os.path.exists(os.path.join(self.output_dir, item[3])) and os.path.getsize(os.path.join(self.output_dir, item[3])) > 0
            )
            total = self.total_expected or len(self.segments_data)

        self.finished.emit(success_count, total)


class AudioCompileWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str) # success, file_path or error message

    def __init__(self, valid_segs_data, file_path, bitrate="320k"):
        super().__init__()
        self.valid_segs_data = valid_segs_data # list of tuples: (audio_path, start_ms, end_ms, duration_ms)
        self.file_path = file_path
        self.bitrate = bitrate or "320k"

    def run(self):
        try:
            from concurrent.futures import ThreadPoolExecutor
            
            total_items = len(self.valid_segs_data)
            if total_items == 0:
                self.finished.emit(False, "គ្មានទិន្នន័យសំឡេងត្រូវបញ្ចូលទេ។")
                return

            max_duration_ms = 0
            for item in self.valid_segs_data:
                if len(item) >= 5:
                    _, audio_path, start_ms, end_ms, duration_ms = item[:5]
                elif len(item) == 4:
                    if isinstance(item[0], int):
                        _, audio_path, start_ms, end_ms = item
                        duration_ms = end_ms - start_ms
                    else:
                        audio_path, start_ms, end_ms, duration_ms = item
                else:
                    audio_path = item[0]
                    start_ms = item[1] if len(item) > 1 else 0
                    end_ms = item[2] if len(item) > 2 else start_ms + 1000
                    duration_ms = end_ms - start_ms
                play_end_ms = start_ms + duration_ms
                max_duration_ms = max(max_duration_ms, end_ms, play_end_ms)
                
            if max_duration_ms == 0:
                max_duration_ms = 1000
                
            self.progress.emit(f"ទំហំរយ:ពេលសរុបគឺ: {max_duration_ms / 1000.0:.2f} វិនាទី")
            self.progress.emit("កំពុងអានឯកសារសំឡេងទាំងអស់ជាស្រប (Parallel)...")
            
            # Helper function to load clip in parallel
            def load_clip(item):
                idx, audio_path, start_ms = item
                try:
                    clip = AudioSegment.from_file(audio_path)
                    return idx, clip, start_ms
                except Exception:
                    return idx, None, start_ms
                
            items = []
            for i, item in enumerate(self.valid_segs_data):
                if len(item) >= 5:
                    path = item[1]
                    start_ms = item[2]
                elif len(item) == 4:
                    if isinstance(item[0], int):
                        path = item[1]
                        start_ms = item[2]
                    else:
                        path = item[0]
                        start_ms = item[1]
                else:
                    path = item[0]
                    start_ms = item[1] if len(item) > 1 else 0
                items.append((i, path, start_ms))
            
            clips = []
            max_workers = min(16, (os.cpu_count() or 4) * 2)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                clips = list(executor.map(load_clip, items))
                
            # Reorder clips to match original timeline indices
            clips = [c for c in clips if c[1] is not None]
            clips.sort(key=lambda x: x[0])
            
            if not clips:
                self.finished.emit(False, "មិនអាចអានឯកសារសំឡេងបានឡើយ។")
                return

            # Determine the common audio properties dynamically from the first clip, fallback to 24000
            frame_rate = 24000
            sample_width = 2
            channels = 1
            if clips:
                first_clip = clips[0][1]
                frame_rate = first_clip.frame_rate
                sample_width = first_clip.sample_width
                channels = first_clip.channels
                
            frame_width = sample_width * channels
            total_frames = int(frame_rate * max_duration_ms / 1000.0)
            master_bytes = bytearray(total_frames * frame_width)
            
            import audioop
            
            for i, clip, start_ms in clips:
                self.progress.emit(f"កំពុងបញ្ចូលជួរទី {i+1}...")
                
                # Align clip properties if they differ from the master track (should be identical usually)
                if clip.frame_rate != frame_rate or clip.sample_width != sample_width or clip.channels != channels:
                    clip = clip.set_frame_rate(frame_rate).set_channels(channels).set_sample_width(sample_width)
                
                clip_raw = clip.raw_data
                clip_len_bytes = len(clip_raw)
                
                start_frame = int(frame_rate * start_ms / 1000.0)
                start_byte = start_frame * frame_width
                end_byte = start_byte + clip_len_bytes
                
                if end_byte > len(master_bytes):
                    master_bytes.extend(b'\x00' * (end_byte - len(master_bytes)))
                
                master_slice = master_bytes[start_byte:end_byte]
                
                if len(master_slice) == len(clip_raw):
                    mixed_slice = audioop.add(master_slice, clip_raw, sample_width)
                else:
                    trimmed_clip_raw = clip_raw[:len(master_slice)]
                    mixed_slice = audioop.add(master_slice, trimmed_clip_raw, sample_width)
                    
                master_bytes[start_byte:start_byte + len(mixed_slice)] = mixed_slice
                
            # Build the final master AudioSegment from the byte buffer
            master = AudioSegment(
                data=bytes(master_bytes),
                sample_width=sample_width,
                frame_rate=frame_rate,
                channels=channels
            )
                
            fmt = "mp3" if self.file_path.lower().endswith(".mp3") else "wav"
            self.progress.emit("កំពុងនាំចេញឯកសារសំឡេង...")
            if fmt == "mp3":
                master.export(self.file_path, format="mp3", bitrate=self.bitrate)
            else:
                master.export(self.file_path, format=fmt)
            
            self.finished.emit(True, self.file_path)
        except Exception as e:
            self.finished.emit(False, str(e))


class ComboBoxDelegate(QStyledItemDelegate):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items  # List of tuples: (Display Text, Data Value)

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        for text, data in self.items:
            editor.addItem(text, data)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.UserRole)
        idx = editor.findData(value)
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        text = editor.currentText()
        data = editor.currentData()
        model.setData(index, text, Qt.DisplayRole)
        model.setData(index, data, Qt.UserRole)


class KhmerTTSApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Khmer Subtitle TTS Voiceover Generator (Piseth & Sreymom)")
        self.resize(1200, 780)
        
        self.segments = []
        self.current_highlighted_row = -1
        self.prev_highlighted_row = -1
        self.play_mode = "full"  # "full" or "clip"
        
        # Track loaded SRT details
        self.loaded_srt_path = ""
        self.loaded_srt_base_name = "khmer_voiceover_master"
        
        # Default Output Dir
        self.output_dir = os.path.abspath(os.path.join(os.getcwd(), "audio_output"))
        
        # Audio Player Init
        self.media_player = QMediaPlayer(None, QMediaPlayer.LowLatency)
        self.media_player.positionChanged.connect(self.on_player_position_changed)
        self.media_player.durationChanged.connect(self.on_player_duration_changed)
        self.media_player.stateChanged.connect(self.on_player_state_changed)
        
        self.worker = None
        self.compiled_file_path = ""
        
        # State tracking flags to prevent lag and unnecessary rendering on tab change
        self.srt_text_modified = False
        self.table_modified = False

        # Setup UI layout
        self.init_ui()
        
        # Auto Dark/Light Theme Initialization
        self.light_mode = self.is_system_in_light_mode()
        self.apply_stylesheet()
        
        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self.detect_and_update_theme)
        self.theme_timer.start(2000) # Check every 2 seconds
        
        self.raw_text_edit.textChanged.connect(self.on_raw_text_changed)
        
        # Preload the default text and parse it
        self.raw_text_edit.setPlainText(DEFAULT_SRT_TEXT.strip())
        self.parse_raw_srt()



    def init_ui(self):
        # Main widget & layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Left Panel (Inputs and Settings)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        
        # Title Label
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("🎙️ កម្មវិធីអានសំឡេងខ្មែរ (Khmer TTS)")
        title_label.setFont(QFont("Leelawadee UI", 16, QFont.Bold))
        title_label.setStyleSheet("color: #00b4d8; margin-bottom: 5px;")
        title_layout.addWidget(title_label)
        left_layout.addWidget(title_container)
        
        # Editor Splitter (Vertical) for Table and Raw SRT
        self.editor_splitter = QSplitter(Qt.Vertical)
        
        # Upper container (Table Editor)
        table_container = QWidget()
        table_container_layout = QVBoxLayout(table_container)
        table_container_layout.setContentsMargins(0, 0, 0, 0)
        table_container_layout.setSpacing(8)
        
        table_label = QLabel("📋 តារាងកែសម្រួលអត្ថបទរង (Subtitle Table Editor)")
        table_label.setFont(QFont("Leelawadee UI", 11, QFont.Bold))
        table_label.setStyleSheet("color: #00b4d8;")
        table_container_layout.addWidget(table_label)
        
        # Table UI
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "ល.រ (ID)", "ចាប់ផ្តើម (Start)", "បញ្ចប់ (End)", 
            "រយ:ពេល (Target)", "ល្បឿន (Speed)", "សំឡេង (Voice)",
            "Echo", "ប្រវែងសំឡេង (Speech)", "អត្ថបទរង (Subtitle Text)", "ស្ថានភាព (Status)"
        ])
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.verticalScrollBar().setSingleStep(1)
        self.table.horizontalScrollBar().setSingleStep(25)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.verticalHeader().setHighlightSections(False)
        self.table.setWordWrap(False)
        if self.table.viewport():
            self.table.viewport().setAttribute(Qt.WA_StaticContents, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemChanged.connect(self.on_table_item_changed)
        self.table.doubleClicked.connect(self.play_selected_row_audio)
        
        # Set combobox delegates for columns 5 and 6
        self.voice_delegate = ComboBoxDelegate([
            ("Auto (ស្វ័យប្រវត្តិ)", "Auto"),
            ("Sreymom (ស្រីម៉ុម)", "Sreymom"),
            ("Piseth (ពិសិដ្ឋ)", "Piseth")
        ], self.table)
        self.table.setItemDelegateForColumn(5, self.voice_delegate)
        
        self.echo_delegate = ComboBoxDelegate([
            ("Auto (ស្វ័យប្រវត្តិ)", "Auto"),
            ("Yes (មាន)", "Yes"),
            ("No (គ្មាន)", "No")
        ], self.table)
        self.table.setItemDelegateForColumn(6, self.echo_delegate)
        
        table_container_layout.addWidget(self.table)
        
        # Table modification controls
        table_controls = QHBoxLayout()
        self.btn_add_row = QPushButton("➕ បន្ថែមជួរ\n(Add)")
        self.btn_add_row.setObjectName("secondaryBtn")
        self.btn_add_row.clicked.connect(self.add_row)
        
        self.btn_delete_row = QPushButton("❌ លុបជួរ\n(Delete)")
        self.btn_delete_row.setObjectName("dangerBtn")
        self.btn_delete_row.clicked.connect(self.delete_row)
        
        self.btn_clear_all = QPushButton("🧹 សម្អាតទាំងអស់\n(Clear)")
        self.btn_clear_all.setObjectName("secondaryBtn")
        self.btn_clear_all.clicked.connect(self.clear_all_rows)
        
        table_controls.addWidget(self.btn_add_row)
        table_controls.addWidget(self.btn_delete_row)
        table_controls.addWidget(self.btn_clear_all)
        table_container_layout.addLayout(table_controls)
        
        # Lower container (Raw SRT Code Editor)
        raw_container = QWidget()
        raw_container_layout = QVBoxLayout(raw_container)
        raw_container_layout.setContentsMargins(0, 0, 0, 0)
        raw_container_layout.setSpacing(8)
        
        raw_label = QLabel("📝 កូដ SRT ដើម (Raw SRT Code Editor)")
        raw_label.setFont(QFont("Leelawadee UI", 11, QFont.Bold))
        raw_label.setStyleSheet("color: #00b4d8;")
        raw_container_layout.addWidget(raw_label)
        
        self.raw_text_edit = QTextEdit()
        self.raw_text_edit.setPlaceholderText("សូមបិទភ្ជាប់អត្ថបទកូដ SRT នៅទីនេះ...")
        self.raw_text_edit.setMinimumHeight(120)
        raw_container_layout.addWidget(self.raw_text_edit)
        
        # Raw tab actions layout
        raw_actions_layout = QHBoxLayout()
        
        self.btn_import_file = QPushButton("📂 នាំចូលឯកសារ SRT/TXT\n(Import File)")
        self.btn_import_file.setObjectName("secondaryBtn")
        self.btn_import_file.clicked.connect(self.import_srt_file)
        raw_actions_layout.addWidget(self.btn_import_file)
        
        self.btn_parse = QPushButton("⚙️ បំប្លែងទៅជាតារាង\n(Parse SRT to Table)")
        self.btn_parse.clicked.connect(self.parse_raw_srt)
        raw_actions_layout.addWidget(self.btn_parse)
        
        self.btn_update_raw = QPushButton("🔄 ធ្វើបច្ចុប្បន្នភាពកូដ SRT\n(Sync Table to SRT)")
        self.btn_update_raw.setObjectName("secondaryBtn")
        self.btn_update_raw.clicked.connect(self.update_raw_srt_from_table)
        raw_actions_layout.addWidget(self.btn_update_raw)
        
        raw_container_layout.addLayout(raw_actions_layout)
        
        # Add panes to splitter
        self.editor_splitter.addWidget(table_container)
        self.editor_splitter.addWidget(raw_container)
        self.editor_splitter.setSizes([450, 200])
        
        left_layout.addWidget(self.editor_splitter)
        
        # Speech Settings Box
        settings_group = QGroupBox("⚙️ ការកំណត់សំឡេងអាន (Voice Settings)")
        settings_form = QFormLayout(settings_group)
        settings_form.setSpacing(10)
        
        # Theme Controls
        theme_layout = QHBoxLayout()
        self.auto_theme_cb = QCheckBox("ស្វែងរកពណ៌ផ្ទៃស្វ័យប្រវត្ត (Auto Theme)")
        self.auto_theme_cb.setChecked(True)
        
        self.btn_theme = QPushButton("🌗 ប្តូរពណ៌ផ្ទៃ\n(Toggle Theme)")
        self.btn_theme.setObjectName("secondaryBtn")
        self.btn_theme.clicked.connect(self.toggle_theme_manually)
        
        theme_layout.addWidget(self.auto_theme_cb)
        theme_layout.addWidget(self.btn_theme)
        settings_form.addRow(QLabel("ពណ៌ផ្ទៃ (App Theme):"), theme_layout)
        
        # Voice Selector
        self.voice_combo = QComboBox()
        self.voice_combo.addItem("Sreymom - ស្រីម៉ុម (Female)", "km-KH-SreymomNeural")
        self.voice_combo.addItem("Piseth - ពិសិដ្ឋ (Male)", "km-KH-PisethNeural")
        self.voice_combo.currentIndexChanged.connect(self.update_auto_voice_table_display)
        settings_form.addRow(QLabel("ជ្រើសរើសសំឡេង (Voice):"), self.voice_combo)
        
        # Speed Slider
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(-50, 100)
        self.speed_slider.setValue(20)  # Set default speed to +20%
        self.speed_label = QLabel("+20%")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(f"{v:+d}%"))
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(self.speed_slider)
        speed_layout.addWidget(self.speed_label)
        settings_form.addRow(QLabel("ល្បឿនរួម (Global Speed):"), speed_layout)
        
        # Auto Speed Option
        self.auto_speed_cb = QCheckBox("ល្បឿនអានស្វ័យប្រវត្តិតាមរយៈពេល (Auto-adjust speed to fit Target Duration)")
        self.auto_speed_cb.setChecked(False)
        self.auto_speed_cb.stateChanged.connect(self.on_auto_speed_toggled)
        settings_form.addRow(QLabel(""), self.auto_speed_cb)
        
        # Auto Save Synchronized Audio Option
        self.auto_save_sync_audio_cb = QCheckBox("នាំចេញសំឡេងរួមដោយស្វ័យប្រវត្តិ (Auto-save synchronized audio on completion)")
        self.auto_save_sync_audio_cb.setChecked(False)
        settings_form.addRow(QLabel(""), self.auto_save_sync_audio_cb)
        
        # Pitch Slider
        self.pitch_slider = QSlider(Qt.Horizontal)
        self.pitch_slider.setRange(-50, 50)
        self.pitch_slider.setValue(0)
        self.pitch_label = QLabel("+0Hz")
        self.pitch_slider.valueChanged.connect(lambda v: self.pitch_label.setText(f"{v:+d}Hz"))
        pitch_layout = QHBoxLayout()
        pitch_layout.addWidget(self.pitch_slider)
        pitch_layout.addWidget(self.pitch_label)
        settings_form.addRow(QLabel("កម្រិតសំឡេង (Pitch):"), pitch_layout)

        # Bitrate / Audio Quality Selector
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItem("💎 320 kbps (គុណភាពច្បាស់បំផុត - Studio Quality)", "320k")
        self.bitrate_combo.addItem("✨ 256 kbps (គុណភាពខ្ពស់ - High Quality)", "256k")
        self.bitrate_combo.addItem("🎧 192 kbps (គុណភាពស្តង់ដារ - Standard Quality)", "192k")
        self.bitrate_combo.addItem("📁 128 kbps (ទំហំឯកសារតូច - Compact Size)", "128k")
        settings_form.addRow(QLabel("គុណភាពសំឡេង (Quality):"), self.bitrate_combo)

        # Output Directory Browser
        self.dir_input = QLineEdit(self.output_dir)
        self.btn_browse = QPushButton("📁 បើក\n(Browse)")
        self.btn_browse.setObjectName("secondaryBtn")
        self.btn_browse.clicked.connect(self.browse_output_dir)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.btn_browse)
        settings_form.addRow(QLabel("ទីតាំងរក្សាទុក (Output Dir):"), dir_layout)
        
        left_layout.addWidget(settings_group)
        
        # Right Panel (Execution, Compilation, Playback Sync)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        
        # Task Operations Box
        ops_group = QGroupBox("⚡ ដំណើរការបង្កើតសំឡេង (TTS & Export Operations)")
        ops_layout = QVBoxLayout(ops_group)
        ops_layout.setSpacing(8)
        
        self.btn_gen_all = QPushButton("🎙️ បង្កើតសំឡេងគ្រប់ជួរទាំងអស់\n(Generate All)")
        self.btn_gen_all.clicked.connect(self.generate_all_voices)
        ops_layout.addWidget(self.btn_gen_all)
        
        self.btn_gen_selected = QPushButton("⚡ បង្កើតសំឡេងជួរដែលជ្រើសរើស\n(Generate Selected)")
        self.btn_gen_selected.setObjectName("secondaryBtn")
        self.btn_gen_selected.clicked.connect(self.generate_selected_voice)
        ops_layout.addWidget(self.btn_gen_selected)
        
        self.btn_pause_resume = QPushButton("⏸️ ផ្អាកការបង្កើត\n(Pause)")
        self.btn_pause_resume.setObjectName("secondaryBtn")
        self.btn_pause_resume.clicked.connect(self.toggle_pause_resume_tts)
        self.btn_pause_resume.setEnabled(False)
        ops_layout.addWidget(self.btn_pause_resume)
        
        self.btn_compile_audio = QPushButton("💾 បញ្ចូលគ្នាជាសំឡេងរួម\n(Export Synchronized Audio)")
        self.btn_compile_audio.clicked.connect(self.compile_master_audio)
        ops_layout.addWidget(self.btn_compile_audio)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        ops_layout.addWidget(self.progress_bar)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFixedHeight(120)
        self.log_output.setPlaceholderText("ស្ថានភាពការងារនឹងបង្ហាញនៅទីនេះ...")
        ops_layout.addWidget(self.log_output)
        
        right_layout.addWidget(ops_group)
        
        # (Active Subtitle banner removed per request)
        
        # Audio Player Controls Box
        player_group = QGroupBox("🔊 ផ្ទាំងបញ្ជាលេងសំឡេង (Audio Player Controls)")
        player_layout = QVBoxLayout(player_group)
        player_layout.setSpacing(8)
        
        # Seek slider and timer label
        seek_layout = QHBoxLayout()
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderMoved.connect(self.on_seek_slider_moved)
        
        self.time_label = QLabel("00:00 / 00:00")
        seek_layout.addWidget(self.seek_slider)
        seek_layout.addWidget(self.time_label)
        player_layout.addLayout(seek_layout)
        
        # Controls Row
        ctrl_row = QHBoxLayout()
        self.btn_play_selected = QPushButton("▶️ ចាក់ជួរដែលរើស\n(Play Clip)")
        self.btn_play_selected.setObjectName("secondaryBtn")
        self.btn_play_selected.clicked.connect(self.play_selected_row_audio)
        
        self.btn_play_full = QPushButton("🎵 ចាក់សំឡេងរួម\n(Play Full Sequence)")
        self.btn_play_full.clicked.connect(self.play_full_sequence)
        
        self.btn_stop = QPushButton("⏹️ ឈប់\n(Stop)")
        self.btn_stop.setObjectName("dangerBtn")
        self.btn_stop.clicked.connect(self.stop_playback)
        
        ctrl_row.addWidget(self.btn_play_selected)
        ctrl_row.addWidget(self.btn_play_full)
        ctrl_row.addWidget(self.btn_stop)
        player_layout.addLayout(ctrl_row)
        
        # Volume slider row
        vol_row = QHBoxLayout()
        vol_label = QLabel("🔊 កម្រិតសំឡេង:")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(150)
        self.media_player.setVolume(70)
        self.volume_slider.valueChanged.connect(self.media_player.setVolume)
        
        vol_row.addWidget(vol_label)
        vol_row.addWidget(self.volume_slider)
        vol_row.addStretch()
        
        player_layout.addLayout(vol_row)
        right_layout.addWidget(player_group)
        
        # Combine Left and Right using QSplitter for responsiveness
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 500])
        main_layout.addWidget(splitter)

    def log(self, text):
        self.log_output.append(text)
        self.log_output.ensureCursorVisible()

    # Output directory browser
    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "ជ្រើសរើសតៅកន្លែងរក្សាទុក", self.output_dir)
        if dir_path:
            self.output_dir = os.path.abspath(dir_path)
            self.dir_input.setText(self.output_dir)
            self.log(f"បានប្តូរទីតាំងរក្សាទុកទៅកាន់: {self.output_dir}")

    def import_srt_file(self):
        """Open a file dialog to import an external .srt or .txt file and parse it into the table."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "ជ្រើសរើសឯកសារ SRT ឬ TEXT", "", 
            "Subtitle/Text Files (*.srt *.txt);;SRT Files (*.srt);;Text Files (*.txt);;All Files (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                srt_content = f.read()
            
            # Save loaded file details
            self.loaded_srt_path = file_path
            self.loaded_srt_base_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # Set the default output directory to the imported file's directory
            self.output_dir = os.path.abspath(os.path.dirname(file_path))
            self.dir_input.setText(self.output_dir)
            self.log(f"បានប្តូរទីតាំងរក្សាទុកទៅតាមឯកសារនាំចូល: {self.output_dir}")
            
            self.raw_text_edit.setPlainText(srt_content.strip())
            self.log(f"បានដាក់ឱ្យចូល SRT file: {file_path}")
            self.parse_raw_srt()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"មិនអាចដាក់ឱ្យចូល SRT បាន: {e}")

    # Toggle Auto speed checkbox logic
    def on_auto_speed_toggled(self, state):
        is_checked = (state == Qt.Checked)
        default_val = "Auto" if is_checked else "Default"
        for seg in self.segments:
            # If the segment uses default auto-mapping, update it
            if seg.speed_str == "Default" or seg.speed_str.startswith("Auto"):
                seg.speed_str = default_val
        self.rebuild_table_ui()
        self.log(f"បានប្តូររបៀបល្បឿនអានរួមទៅជា: {'ស្វ័យប្រវត្តិតាមរយៈពេល (Auto)' if is_checked else 'កំណត់ដោយខ្លួនឯង (Manual)'}")

    def on_raw_text_changed(self):
        self.srt_text_modified = True


    # Parse raw SRT from text area to segment list & table
    def parse_raw_srt(self):
        srt_text = self.raw_text_edit.toPlainText().strip()
        if not srt_text:
            return
            
        srt_text = srt_text.replace('\r\n', '\n')
        
        # Check if the text contains standard SRT timeline markers
        is_srt = "-->" in srt_text
        
        new_segments = []
        parsed_count = 0
        is_auto = self.auto_speed_cb.isChecked()
        default_speed = "Auto" if is_auto else "Default"
        
        if is_srt:
            # 1. Parse as standard SRT format
            blocks = re.split(r'\n\s*\n', srt_text)
            
            # Build lookup map for old segments to make matching O(N) instead of O(N^2)
            old_segments_map = {}
            for old_seg in self.segments:
                old_segments_map[(old_seg.index, old_seg.start_str, old_seg.end_str, old_seg.text)] = old_seg
                
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                
                lines = block.split('\n')
                if len(lines) < 3:
                    continue
                
                # Subtitle ID
                try:
                    idx = int(lines[0].strip())
                except ValueError:
                    idx = len(new_segments) + 1
                    
                # Time line
                time_line = lines[1].strip()
                time_match = re.match(r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})', time_line)
                if not time_match:
                    continue
                    
                start_str = time_match.group(1).replace('.', ',')
                end_str = time_match.group(2).replace('.', ',')
                
                # Subtitle text
                sub_text = "\n".join(lines[2:]).strip()
                
                # Preserve old values if matching
                key = (idx, start_str, end_str, sub_text)
                old_seg = old_segments_map.get(key)
                if old_seg:
                    audio_path = old_seg.audio_path
                    duration_ms = old_seg.duration_ms
                    status = old_seg.status
                    speed_str = old_seg.speed_str
                    voice = old_seg.voice
                    echo = old_seg.echo
                else:
                    audio_path = ""
                    duration_ms = 0
                    status = "Ready"
                    speed_str = default_speed
                    voice = "Auto"
                    echo = "Auto"
                
                new_segments.append(SubtitleSegment(
                    index=idx,
                    start_str=start_str,
                    end_str=end_str,
                    start_ms=timestamp_to_ms(start_str),
                    end_ms=timestamp_to_ms(end_str),
                    text=sub_text,
                    speed_str=speed_str,
                    audio_path=audio_path,
                    duration_ms=duration_ms,
                    status=status,
                    voice=voice,
                    echo=echo
                ))
                parsed_count += 1
            
            self.log(f"បានវិភាគ Subtitle SRT រួចរាល់: ចំនួន {parsed_count} ជួរ")
        else:
            # 2. Parse as plain text (line-by-line format)
            raw_lines = srt_text.split('\n')
            current_ms = 0
            
            for line in raw_lines:
                line_content = line.strip()
                if not line_content:
                    continue
                
                idx = len(new_segments) + 1
                
                # Automatically calculate sequential timestamps (3 seconds per line, 1s gap)
                start_ms = current_ms
                end_ms = start_ms + 3000
                start_str = ms_to_timestamp(start_ms)
                end_str = ms_to_timestamp(end_ms)
                
                # Check if we already have this segment in self.segments to preserve values
                old_seg = None
                for s in self.segments:
                    if s.index == idx and s.text == line_content:
                        old_seg = s
                        break
                        
                if old_seg:
                    audio_path = old_seg.audio_path
                    duration_ms = old_seg.duration_ms
                    status = old_seg.status
                    speed_str = old_seg.speed_str
                    voice = old_seg.voice
                    echo = old_seg.echo
                else:
                    audio_path = ""
                    duration_ms = 0
                    status = "Ready"
                    speed_str = default_speed
                    voice = "Auto"
                    echo = "Auto"
                    
                new_segments.append(SubtitleSegment(
                    index=idx,
                    start_str=start_str,
                    end_str=end_str,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=line_content,
                    speed_str=speed_str,
                    audio_path=audio_path,
                    duration_ms=duration_ms,
                    status=status,
                    voice=voice,
                    echo=echo
                ))
                parsed_count += 1
                current_ms = end_ms + 1000 # 1 second delay between lines
                
            self.log(f"បានវិភាគ Plain Text (អត្ថបទបន្ទាត់នីមួយៗ): ចំនួន {parsed_count} ជួរ")
            
        self.segments = new_segments
        self.rebuild_table_ui()
        self.srt_text_modified = False
        self.table_modified = False

    # Format table data back to raw SRT editor
    def update_raw_srt_from_table(self):
        # Temporarily disconnect textChanged to avoid setting srt_text_modified = True when updating raw text from table
        try:
            self.raw_text_edit.textChanged.disconnect(self.on_raw_text_changed)
        except TypeError:
            pass
            
        try:
            lines = []
            for seg in self.segments:
                lines.append(str(seg.index))
                lines.append(f"{seg.start_str} --> {seg.end_str}")
                lines.append(seg.text)
                lines.append("")
            self.raw_text_edit.setPlainText("\n".join(lines).strip())
            self.srt_text_modified = False
            self.table_modified = False
        finally:
            self.raw_text_edit.textChanged.connect(self.on_raw_text_changed)

    def format_voice_display(self, seg):
        if seg.voice == "Auto":
            detected_voice, _ = parse_voice_and_echo_from_text(seg.text, default_voice="Global")
            if detected_voice == "Sreymom":
                return "Auto (ស្រីម៉ុម)"
            elif detected_voice == "Piseth":
                return "Auto (ពិសិដ្ឋ)"
            else:
                if hasattr(self, 'voice_combo') and self.voice_combo:
                    data = self.voice_combo.currentData()
                    if data == "km-KH-SreymomNeural":
                        return "Auto (ស្រីម៉ុម)"
                    elif data == "km-KH-PisethNeural":
                        return "Auto (ពិសិដ្ឋ)"
                return "Auto (ស្វ័យប្រវត្តិ)"
        elif seg.voice == "Sreymom":
            return "Sreymom (ស្រីម៉ុម)"
        elif seg.voice == "Piseth":
            return "Piseth (ពិសិដ្ឋ)"
        return seg.voice

    def format_echo_display(self, seg):
        if seg.echo == "Auto":
            _, detected_echo = parse_voice_and_echo_from_text(seg.text)
            if detected_echo:
                return "Auto (មាន Echo)"
            else:
                return "Auto (គ្មាន Echo)"
        elif seg.echo == "Yes":
            return "Yes (មាន Echo)"
        elif seg.echo == "No":
            return "No (គ្មាន Echo)"
        return seg.echo

    def update_auto_voice_table_display(self):
        if not hasattr(self, 'table') or not self.segments:
            return
        self.table.blockSignals(True)
        for r, seg in enumerate(self.segments):
            if seg.voice == "Auto":
                item = self.table.item(r, 5)
                if item:
                    item.setText(self.format_voice_display(seg))
        self.table.blockSignals(False)

    # Build or Rebuild the Table Widget contents
    def rebuild_table_ui(self):
        self.table.setUpdatesEnabled(False)
        self.table.itemChanged.disconnect(self.on_table_item_changed)
        try:
            self.table.setRowCount(0)
            self.table.setRowCount(len(self.segments))

            brush_overflow = QBrush(QColor("#ffb703"))
            brush_success = QBrush(QColor("#2ec4b6"))
            brush_error = QBrush(QColor("#e71d36"))
            brush_light_even = QBrush(QColor("#ffffff"))
            brush_light_odd = QBrush(QColor("#f4f4f9"))
            brush_dark_even = QBrush(QColor("#181824"))
            brush_dark_odd = QBrush(QColor("#1c1c2a"))
            brush_light_text = QBrush(QColor("#1a1a1f"))
            brush_dark_text = QBrush(QColor("#f8f9fa"))

            text_brush = brush_light_text if self.light_mode else brush_dark_text
            
            for r, seg in enumerate(self.segments):
                # Index (read-only)
                idx_item = QTableWidgetItem(str(seg.index))
                idx_item.setFlags(idx_item.flags() & ~Qt.ItemIsEditable)
                idx_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 0, idx_item)
                
                # Start
                start_item = QTableWidgetItem(seg.start_str)
                start_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 1, start_item)
                
                # End
                end_item = QTableWidgetItem(seg.end_str)
                end_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 2, end_item)
                
                # Target Duration (read-only)
                target_sec = (seg.end_ms - seg.start_ms) / 1000.0
                target_item = QTableWidgetItem(f"{target_sec:.2f}s")
                target_item.setFlags(target_item.flags() & ~Qt.ItemIsEditable)
                target_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 3, target_item)
                
                # Speed Rate (editable per row!)
                speed_item = QTableWidgetItem(seg.speed_str)
                speed_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 4, speed_item)
                
                # Voice (col 5)
                voice_text = self.format_voice_display(seg)
                voice_item = QTableWidgetItem(voice_text)
                voice_item.setData(Qt.UserRole, seg.voice)
                voice_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 5, voice_item)
                
                # Echo (col 6)
                echo_text = self.format_echo_display(seg)
                echo_item = QTableWidgetItem(echo_text)
                echo_item.setData(Qt.UserRole, seg.echo)
                echo_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, 6, echo_item)
                
                # Speech Duration (read-only) (col 7)
                speech_sec = seg.duration_ms / 1000.0
                speech_item = QTableWidgetItem(f"{speech_sec:.2f}s" if seg.duration_ms > 0 else "-")
                speech_item.setFlags(speech_item.flags() & ~Qt.ItemIsEditable)
                speech_item.setTextAlignment(Qt.AlignCenter)
                # Warn user if speech overflows the timeline target window
                if seg.duration_ms > (seg.end_ms - seg.start_ms):
                    speech_item.setForeground(brush_overflow)
                    seg.status = "Overflow"
                self.table.setItem(r, 7, speech_item)
                
                # Subtitle Text (editable) (col 8)
                text_item = QTableWidgetItem(seg.text)
                self.table.setItem(r, 8, text_item)
                
                # Status (read-only) (col 9)
                status_item = QTableWidgetItem(seg.status)
                status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
                status_item.setTextAlignment(Qt.AlignCenter)
                if seg.status == "Success":
                    status_item.setForeground(brush_success)
                elif seg.status == "Error":
                    status_item.setForeground(brush_error)
                elif seg.status == "Overflow":
                    status_item.setForeground(brush_overflow)
                self.table.setItem(r, 9, status_item)
                
                # Set background color based on alternating rows
                if self.light_mode:
                    bg_brush = brush_light_even if r % 2 == 0 else brush_light_odd
                else:
                    bg_brush = brush_dark_even if r % 2 == 0 else brush_dark_odd
                    
                for c in range(10):
                    item = self.table.item(r, c)
                    if item:
                        item.setBackground(bg_brush)
                        if c != 7 and c != 9:
                            item.setForeground(text_brush)
        finally:
            self.table.itemChanged.connect(self.on_table_item_changed)
            self.table.setUpdatesEnabled(True)

    # Listen to changes in the editable cells
    def on_table_item_changed(self, item):
        row = item.row()
        col = item.column()
        val = item.text().strip()
        
        seg = self.segments[row]
        
        self.table.itemChanged.disconnect(self.on_table_item_changed)
        try:
            self.table_modified = True
            if col == 1:  # Start string
                if self.is_valid_timestamp(val):
                    seg.start_str = val
                    seg.start_ms = timestamp_to_ms(val)
                    target_sec = (seg.end_ms - seg.start_ms) / 1000.0
                    self.table.item(row, 3).setText(f"{target_sec:.2f}s")
                    self.update_speech_dur_warning(row)
                else:
                    item.setText(seg.start_str)
            elif col == 2:  # End string
                if self.is_valid_timestamp(val):
                    seg.end_str = val
                    seg.end_ms = timestamp_to_ms(val)
                    target_sec = (seg.end_ms - seg.start_ms) / 1000.0
                    self.table.item(row, 3).setText(f"{target_sec:.2f}s")
                    self.update_speech_dur_warning(row)
                else:
                    item.setText(seg.end_str)
            elif col == 4:  # Speed string (per row)
                seg.speed_str = val
            elif col == 5:  # Voice (from delegate)
                voice_val = item.data(Qt.UserRole)
                if voice_val:
                    seg.voice = voice_val
                    item.setText(self.format_voice_display(seg))
                    self.log(f"បានប្តូរសំឡេងជួរ {row + 1} ទៅជា: {seg.voice}")
            elif col == 6:  # Echo (from delegate)
                echo_val = item.data(Qt.UserRole)
                if echo_val:
                    seg.echo = echo_val
                    item.setText(self.format_echo_display(seg))
                    self.log(f"បានប្តូរ Echo ជួរ {row + 1} ទៅជា: {seg.echo}")
            elif col == 8:  # Text
                seg.text = val
                if seg.voice == "Auto":
                    v_item = self.table.item(row, 5)
                    if v_item:
                        v_item.setText(self.format_voice_display(seg))
                if seg.echo == "Auto":
                    e_item = self.table.item(row, 6)
                    if e_item:
                        e_item.setText(self.format_echo_display(seg))
        finally:
            self.table.itemChanged.connect(self.on_table_item_changed)

    def is_valid_timestamp(self, ts):
        return bool(re.match(r'^\d{2}:\d{2}:\d{2}[.,]\d{3}$', ts))

    def update_speech_dur_warning(self, row):
        seg = self.segments[row]
        speech_item = self.table.item(row, 7)
        status_item = self.table.item(row, 9)
        
        if not speech_item or not status_item:
            return
            
        speech_sec = seg.duration_ms / 1000.0
        if seg.duration_ms > 0:
            speech_item.setText(f"{speech_sec:.2f}s")
            
            if seg.duration_ms > (seg.end_ms - seg.start_ms):
                speech_item.setForeground(QBrush(QColor("#ffb703")))
                seg.status = "Overflow"
                status_item.setText("Overflow")
                status_item.setForeground(QBrush(QColor("#ffb703")))
            else:
                speech_item.setForeground(QBrush(QColor("#f8f9fa")))
                seg.status = "Success"
                status_item.setText("Success")
                status_item.setForeground(QBrush(QColor("#2ec4b6")))


    # Modify rows (Add/Delete/Clear)
    def add_row(self):
        idx = len(self.segments) + 1
        if self.segments:
            last = self.segments[-1]
            start_ms = last.end_ms + 1000
            end_ms = start_ms + 2000
        else:
            start_ms = 0
            end_ms = 2000
            
        start_str = ms_to_timestamp(start_ms)
        end_str = ms_to_timestamp(end_ms)
        
        speed_str = "Auto" if self.auto_speed_cb.isChecked() else "Default"
        
        self.segments.append(SubtitleSegment(
            index=idx,
            start_str=start_str,
            end_str=end_str,
            start_ms=start_ms,
            end_ms=end_ms,
            text="អត្ថបទរងថ្មី (New Line)",
            speed_str=speed_str,
            status="Ready",
            voice="Auto",
            echo="Auto"
        ))
        self.table_modified = True
        self.rebuild_table_ui()
        self.log(f"បានបន្ថែមជួរថ្មី លេខ {idx}")

    def delete_row(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "ការព្រមាន", "សូមជ្រើសរើសជួរណាមួយនៅក្នុងតារាងដើម្បីលុប!")
            return
            
        row_idx = selected_rows[0].row()
        del_seg = self.segments.pop(row_idx)
        
        for i in range(row_idx, len(self.segments)):
            self.segments[i].index = i + 1
            
        self.table_modified = True
        self.rebuild_table_ui()
        self.log(f"បានលុបជួរ លេខ {del_seg.index}")

    def clear_all_rows(self):
        reply = QMessageBox.question(
            self, "បញ្ជាក់", "តើអ្នកពិតជាចង់សម្អាតជួរទាំងអស់មែនទេ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.segments = []
            self.table_modified = True
            self.rebuild_table_ui()
            self.raw_text_edit.clear()
            self.log("បានសម្អាតជួរទាំងអស់រួចរាល់")

    # Generate speech params
    def get_tts_parameters(self):
        voice = self.voice_combo.currentData()
        speed_val = self.speed_slider.value()
        rate_str = f"{speed_val:+d}%"
        pitch_val = self.pitch_slider.value()
        pitch_str = f"{pitch_val:+d}Hz"
        self.output_dir = self.dir_input.text().strip()
        
        return voice, rate_str, pitch_str, self.output_dir

    def get_tts_bitrate(self) -> str:
        if hasattr(self, "bitrate_combo") and self.bitrate_combo.currentData():
            return self.bitrate_combo.currentData()
        return "320k"

    def toggle_pause_resume_tts(self):
        if self.worker and self.worker.isRunning():
            if not self.worker.is_paused:
                self.worker.pause()
                self.btn_pause_resume.setText("▶️ បន្តការបង្កើត\n(Resume)")
                self.log("បានផ្អាកការបង្កើតសំឡេងបណ្តោះអាសន្ន។")
            else:
                self.worker.resume()
                self.btn_pause_resume.setText("⏸️ ផ្អាកការបង្កើត\n(Pause)")
                self.log("បានបន្តដំណើរការបង្កើតសំឡេងឡើងវិញ...")

    def set_gui_enabled(self, enabled, is_generating=False):
        self.btn_gen_all.setEnabled(enabled)
        self.btn_gen_selected.setEnabled(enabled)
        self.btn_compile_audio.setEnabled(enabled)
        self.btn_add_row.setEnabled(enabled)
        self.btn_delete_row.setEnabled(enabled)
        self.btn_clear_all.setEnabled(enabled)
        self.btn_parse.setEnabled(enabled)
        self.btn_import_file.setEnabled(enabled)
        self.btn_update_raw.setEnabled(enabled)
        self.voice_combo.setEnabled(enabled)
        self.speed_slider.setEnabled(enabled)
        self.auto_speed_cb.setEnabled(enabled)
        self.auto_save_sync_audio_cb.setEnabled(enabled)
        self.pitch_slider.setEnabled(enabled)
        self.dir_input.setEnabled(enabled)
        self.btn_browse.setEnabled(enabled)
                
        if not enabled:
            if is_generating:
                self.btn_gen_all.setText("⛔ បោះបង់ការបង្កើតសំឡេង\n(Cancel)")
                self.btn_gen_all.setEnabled(True)
                self.btn_pause_resume.setEnabled(True)
                self.btn_pause_resume.setText("⏸️ ផ្អាកការបង្កើត\n(Pause)")
            else:
                self.btn_gen_all.setEnabled(False)
                self.btn_pause_resume.setEnabled(False)
        else:
            self.btn_gen_all.setText("🎙️ បង្កើតសំឡេងគ្រប់ជួរទាំងអស់\n(Generate All)")
            self.btn_pause_resume.setEnabled(False)
            self.btn_pause_resume.setText("⏸️ ផ្អាកការបង្កើត\n(Pause)")

    def generate_all_voices(self):
        if self.worker and self.worker.isRunning():
            self.log("កំពុងបោះបង់ការងារបង្កើតសំឡេង...")
            self.worker.stop()
            return

        if not self.segments:
            QMessageBox.warning(self, "ការព្រមាន", "មិនមានទិន្នន័យដើម្បីបង្កើតសំឡេងទេ!")
            return
            
        voice, rate, pitch, output_dir = self.get_tts_parameters()
        
        if hasattr(self, 'loaded_srt_path') and self.loaded_srt_path:
            default_base = self.loaded_srt_base_name
        else:
            default_base = "sub"
        
        worker_data = []
        for seg in self.segments:
            file_name = f"{default_base}_{seg.index:03d}.mp3"
            target_ms = seg.end_ms - seg.start_ms
            
            # Extract clean speed command (strip calculated metrics like "Auto (+12%)" -> "Auto")
            speed_val = seg.speed_str
            if speed_val.startswith("Auto"):
                speed_val = "Auto"
                
            worker_data.append((seg.index, seg.text, file_name, target_ms, speed_val, seg.voice, seg.echo))
            
        self.set_gui_enabled(False, is_generating=True)
        self.progress_bar.setRange(0, len(self.segments))
        self.progress_bar.setValue(0)
        self.log(f"ចាប់ផ្តើមបង្កើតសំឡេងជាមួយសំឡេង: {voice} (Pitch: {pitch})")
        
        self.worker = TTSWorker(worker_data, voice, rate, pitch, output_dir, bitrate=self.get_tts_bitrate())
        self.worker.progress_started.connect(self.on_worker_progress_started)
        self.worker.progress_finished.connect(self.on_worker_progress_finished)
        self.worker.progress_warning.connect(self.on_worker_progress_warning)
        self.worker.progress_error.connect(self.on_worker_progress_error)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def generate_selected_voice(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "ការព្រមាន", "សូមជ្រើសរើសជួរមួយនៅក្នុងតារាងជាមុនសិន!")
            return
            
        row_idx = selected_rows[0].row()
        self.generate_single_voice_by_index(row_idx)

    def generate_single_voice_by_index(self, row_idx):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "ការព្រមាន", "កំពុងដំណើរការបង្កើតសំឡេងផ្សេងទៀត! សូមរង់ចាំ ឬបោះបង់ជាមុនសិន។")
            return
            
        if row_idx < 0 or row_idx >= len(self.segments):
            return
            
        seg = self.segments[row_idx]
        
        voice, rate, pitch, output_dir = self.get_tts_parameters()
        
        if hasattr(self, 'loaded_srt_path') and self.loaded_srt_path:
            default_base = self.loaded_srt_base_name
        else:
            default_base = "sub"
            
        file_name = f"{default_base}_{seg.index:03d}.mp3"
        target_ms = seg.end_ms - seg.start_ms
        speed_val = seg.speed_str
        if speed_val.startswith("Auto"):
            speed_val = "Auto"
            
        worker_data = [(seg.index, seg.text, file_name, target_ms, speed_val, seg.voice, seg.echo)]
        
        self.set_gui_enabled(False, is_generating=True)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.log(f"ចាប់ផ្តើមបង្កើតសំឡេងសម្រាប់ជួរលេខ {seg.index} (Voice: {voice})")
        
        self.worker = TTSWorker(worker_data, voice, rate, pitch, output_dir, bitrate=self.get_tts_bitrate())
        self.worker.progress_started.connect(lambda _: self.on_worker_progress_started(row_idx))
        self.worker.progress_finished.connect(lambda _, fp, dur, ru: self.on_worker_progress_finished(row_idx, fp, dur, ru))
        self.worker.progress_warning.connect(lambda _, warn: self.on_worker_progress_warning(row_idx, warn))
        self.worker.progress_error.connect(lambda _, err: self.on_worker_progress_error(row_idx, err))
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    # Worker callbacks
    def on_worker_progress_started(self, idx):
        self.segments[idx].status = "Generating..."
        status_item = self.table.item(idx, 9)
        if status_item:
            status_item.setText("Generating...")
            status_item.setForeground(QBrush(QColor("#8e8e9f")))
        self.log(f"កំពុងបង្កើតជួរទី {idx + 1}...")

    def on_worker_progress_warning(self, idx, warning_msg):
        self.segments[idx].status = "Retrying..."
        status_item = self.table.item(idx, 9)
        if status_item:
            status_item.setText("Retrying...")
            status_item.setForeground(QBrush(QColor("#ffb703")))
        self.log(f"ការព្រមាននៅជួរទី {idx + 1}: {warning_msg}")

    def on_worker_progress_finished(self, idx, file_path, duration_ms, rate_used):
        seg = self.segments[idx]
        seg.audio_path = file_path
        seg.duration_ms = duration_ms
        seg.status = "Success"
        
        # Display the speed rate calculation if Auto was utilized
        if seg.speed_str.startswith("Auto") or seg.speed_str == "Auto":
            seg.speed_str = f"Auto ({rate_used})"
            
        self.update_row_cells(idx)
        self.progress_bar.setValue(self.progress_bar.value() + 1)
        self.log(f"បង្កើតជួរទី {idx + 1} ជោគជ័យ! ល្បឿន: {rate_used}, ប្រវែង: {duration_ms / 1000.0:.2f}s")

    def on_worker_progress_error(self, idx, error_msg):
        self.segments[idx].status = "Error"
        self.update_row_cells(idx)
        status_item = self.table.item(idx, 9)
        if status_item:
            status_item.setToolTip(error_msg)
        self.progress_bar.setValue(self.progress_bar.value() + 1)
        self.log(f"កំហុសនៅជួរទី {idx + 1}: {error_msg}")

    def on_worker_finished(self, success_count, total_count):
        self.set_gui_enabled(True)
        self.log(f"រួចរាល់! ជោគជ័យ {success_count}/{total_count} ជួរ។")
        if success_count == total_count:
            if self.auto_save_sync_audio_cb.isChecked():
                self.log("កំពុងរក្សាទុកឯកសារសំឡេងរួមដោយស្វ័យប្រវត្តិ (Auto-saving synchronized audio)...")
                self.compile_master_audio(show_dialogs=False)
            QMessageBox.information(self, "ជោគជ័យ", "ការបង្កើតសំឡេងត្រូវបានបញ្ចប់ដោយជោគជ័យ!")

    # Helper method to dynamically update row cells instead of rebuild
    def update_row_cells(self, idx):
        self.table.itemChanged.disconnect(self.on_table_item_changed)
        try:
            seg = self.segments[idx]
            
            # Speed item
            speed_item = self.table.item(idx, 4)
            if speed_item:
                speed_item.setText(seg.speed_str)
                
            # Speech Duration item
            speech_sec = seg.duration_ms / 1000.0
            speech_item = self.table.item(idx, 7)
            if speech_item:
                speech_item.setText(f"{speech_sec:.2f}s" if seg.duration_ms > 0 else "-")
                if seg.duration_ms > (seg.end_ms - seg.start_ms):
                    speech_item.setForeground(QBrush(QColor("#ffb703")))
                    seg.status = "Overflow"
                else:
                    fg_color = QColor("#1a1a1f") if self.light_mode else QColor("#f8f9fa")
                    speech_item.setForeground(QBrush(fg_color))
                    
            # Status item
            status_item = self.table.item(idx, 9)
            if status_item:
                status_item.setText(seg.status)
                if seg.status == "Success":
                    status_item.setForeground(QBrush(QColor("#2ec4b6")))
                elif seg.status == "Error":
                    status_item.setForeground(QBrush(QColor("#e71d36")))
                elif seg.status == "Overflow":
                    status_item.setForeground(QBrush(QColor("#ffb703")))
        except Exception as e:
            print(f"Error updating row cells: {e}")
        finally:
            self.table.itemChanged.connect(self.on_table_item_changed)

    # Merge individual clips into master file using pydub
    def compile_master_audio(self, file_path=None, show_dialogs=True, play_after_compile=False):
        valid_segs = [s for s in self.segments if s.audio_path and os.path.exists(s.audio_path)]
        if not valid_segs:
            if show_dialogs:
                QMessageBox.warning(self, "ការព្រមាន", "មិនទាន់មានឯកសារសំឡេងដែលបានបង្កើតរួចរាល់ទេ! សូមចុច Generate ជាមុនសិន។")
            else:
                self.log("ការព្រមាន: មិនទាន់មានឯកសារសំឡេងដែលបានបង្កើតរួចរាល់ទេ! មិនអាចនាំចេញដោយស្វ័យប្រវត្តិបានទេ។")
            return
            
        if not file_path:
            default_base = self.loaded_srt_base_name if hasattr(self, 'loaded_srt_base_name') else "khmer_voiceover_master"
            if show_dialogs:
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "រក្សាទុកឯកសារសំឡេងរួម", 
                    os.path.join(self.output_dir, f"{default_base}.mp3"),
                    "MP3 Files (*.mp3);;WAV Files (*.wav)"
                )
                if not file_path:
                    return
            else:
                base_name = default_base
                ext = ".mp3"
                file_path = os.path.join(self.output_dir, base_name + ext)
                count = 1
                while os.path.exists(file_path):
                    file_path = os.path.join(self.output_dir, f"{base_name}_{count}{ext}")
                    count += 1
            
        self.show_compile_dialogs = show_dialogs
        self.play_after_compile = play_after_compile
        
        self.set_gui_enabled(False, is_generating=False)
        self.log(f"កំពុងបញ្ជូនឯកសារបញ្ចូលគ្នា និងចងក្រងទៅកាន់ {file_path}...")
        
        # Prepare data for worker
        valid_segs_data = []
        for s in valid_segs:
            sub_idx = getattr(s, 'index', 0)
            valid_segs_data.append((sub_idx, s.audio_path, s.start_ms, s.end_ms, s.duration_ms))
            
        self.compile_worker = AudioCompileWorker(valid_segs_data, file_path, bitrate=self.get_tts_bitrate())
        self.compile_worker.progress.connect(self.log)
        self.compile_worker.finished.connect(self.on_compile_finished)
        self.compile_worker.start()

    def on_compile_finished(self, success, result_path_or_err):
        self.set_gui_enabled(True)
        if success:
            self.compiled_file_path = result_path_or_err
            self.log(f"✅ បានចងក្រង និងរក្សាទុកឯកសាររួមបានសម្រេច: {result_path_or_err}")

            # Automatically delete individual temporary audio clips to save disk space
            if not self.play_after_compile:
                deleted_count = 0
                for seg in self.segments:
                    if seg.audio_path and os.path.exists(seg.audio_path):
                        if os.path.abspath(seg.audio_path) != os.path.abspath(result_path_or_err):
                            try:
                                os.remove(seg.audio_path)
                                seg.audio_path = ""
                                deleted_count += 1
                            except Exception as e:
                                print(f"Failed to delete temporary clip {seg.audio_path}: {e}")
                if deleted_count > 0:
                    self.log(f"បានលុបឯកសារសំឡេងជួរខ្លីៗបណ្តោះអាសន្នចំនួន {deleted_count} រួចរាល់ ដើម្បីកុំឱ្យចង្អៀតកន្លែងរក្សាទុក។")
            
            if self.play_after_compile:
                try:
                    self.play_mode = "full"
                    self.current_highlighted_row = -1
                    
                    url = QUrl.fromLocalFile(os.path.abspath(result_path_or_err))
                    self.media_player.setMedia(QMediaContent(url))
                    self.media_player.play()
                    self.log("កំពុងចាក់សំឡេងរួមជាមួយការបង្ហាញអត្ថបទរង...")
                except Exception as e:
                    self.log(f"កំហុសក្នុងការរៀបចំចាក់: {e}")
                    QMessageBox.critical(self, "កំហុស", f"មិនអាចរៀបចំចាក់បានទេ: {e}")
            else:
                if self.show_compile_dialogs:
                    QMessageBox.information(self, "ជោគជ័យ", f"🎉 បានរក្សាទុកឯកសាររួមនៅ:\n{result_path_or_err}\n\n(បានលុបឯកសារបណ្តោះអាសន្នទាំងអស់ ដើម្បីសន្សំទំហំ Disk)")
        else:
            self.log(f"កំហុសក្នុងការចងក្រងសំឡេង: {result_path_or_err}")
            if self.show_compile_dialogs:
                QMessageBox.critical(self, "កំហុស", f"មិនអាចផ្គុំឯកសារសំឡេងបានទេ:\n{result_path_or_err}")

    # Playback functions
    def play_selected_row_audio(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
            
        row_idx = selected_rows[0].row()
        seg = self.segments[row_idx]
        
        if not seg.audio_path or not os.path.exists(seg.audio_path):
            QMessageBox.warning(self, "ការព្រមាន", f"ជួរលេខ {seg.index} មិនទាន់មានឯកសារសំឡេងទេ! សូមបង្កើតវាជាមុនសិន។")
            return
            
        self.play_mode = "clip"
        self.current_highlighted_row = row_idx
        if hasattr(self, "teleprompter_label"):
            self.teleprompter_label.setText(seg.text)
        
        self.highlight_single_row(row_idx)
        
        self.log(f"ចាក់ឯកសារជួរលេខ: {seg.index}")
        url = QUrl.fromLocalFile(os.path.abspath(seg.audio_path))
        self.media_player.setMedia(QMediaContent(url))
        self.media_player.play()

    def play_full_sequence(self):
        valid_segs = [s for s in self.segments if s.audio_path and os.path.exists(s.audio_path)]
        if not valid_segs:
            QMessageBox.warning(self, "ការព្រមាន", "មិនមានឯកសារសំឡេងដើម្បីចាក់ទេ! សូមចុច Generate គ្រប់ជួរទាំងអស់ជាមុនសិន។")
            return
            
        temp_compiled = os.path.join(self.output_dir, "temp_combined_preview.mp3")
        self.compile_master_audio(file_path=temp_compiled, show_dialogs=False, play_after_compile=True)

    def stop_playback(self):
        self.media_player.stop()
        if hasattr(self, "teleprompter_label"):
            self.teleprompter_label.setText("ឈប់ចាក់សំឡេង")
        self.current_highlighted_row = -1
        self.rebuild_table_ui()

    # Playback handlers
    def on_player_position_changed(self, position):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position)
            
        self.update_time_label(position, self.media_player.duration())
        
        if self.play_mode == "full":
            active_idx = -1
            for idx, seg in enumerate(self.segments):
                play_end = seg.start_ms + max(seg.duration_ms, seg.end_ms - seg.start_ms)
                if seg.start_ms <= position <= play_end:
                    active_idx = idx
                    break
                    
            if active_idx != -1 and active_idx != self.current_highlighted_row:
                self.highlight_single_row(active_idx)

    def on_player_duration_changed(self, duration):
        self.seek_slider.setRange(0, duration)
        self.update_time_label(self.media_player.position(), duration)

    def on_player_state_changed(self, state):
        if state == QMediaPlayer.StoppedState:
            pass

    def on_seek_slider_moved(self, position):
        self.media_player.setPosition(position)

    def update_time_label(self, position, duration):
        pos_sec = position // 1000
        pos_min = pos_sec // 60
        pos_sec %= 60
        
        dur_sec = duration // 1000
        dur_min = dur_sec // 60
        dur_sec %= 60
        
        self.time_label.setText(f"{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}")

    def highlight_single_row(self, row_idx):
        self.table.itemChanged.disconnect(self.on_table_item_changed)
        self.table.setUpdatesEnabled(False)
        try:
            # Only update the previous highlighted row and the new highlighted row
            rows_to_update = [row_idx]
            if hasattr(self, 'prev_highlighted_row') and self.prev_highlighted_row != -1:
                rows_to_update.append(self.prev_highlighted_row)
                
            self.prev_highlighted_row = row_idx
            self.current_highlighted_row = row_idx
            
            for r in rows_to_update:
                if r < 0 or r >= self.table.rowCount():
                    continue
                if self.light_mode:
                    bg_color = QColor("#bde0fe") if r == row_idx else (QColor("#ffffff") if r % 2 == 0 else QColor("#f4f4f9"))
                    fg_color = QColor("#0077b6") if r == row_idx else QColor("#1a1a1f")
                else:
                    bg_color = QColor("#1c2d3d") if r == row_idx else (QColor("#181824") if r % 2 == 0 else QColor("#1c1c2a"))
                    fg_color = QColor("#00b4d8") if r == row_idx else QColor("#f8f9fa")
                
                for c in range(self.table.columnCount()):
                    item = self.table.item(r, c)
                    if item:
                        item.setBackground(QBrush(bg_color))
                        if r != row_idx:
                            # Preserving column statuses on other rows
                            if c == 7: # Speech Duration
                                seg = self.segments[r]
                                if seg.duration_ms > (seg.end_ms - seg.start_ms):
                                    item.setForeground(QBrush(QColor("#ffb703")))
                                    continue
                            elif c == 9: # Status
                                seg = self.segments[r]
                                if seg.status == "Success":
                                    item.setForeground(QBrush(QColor("#2ec4b6")))
                                    continue
                                elif seg.status == "Error":
                                    item.setForeground(QBrush(QColor("#e71d36")))
                                    continue
                                elif seg.status == "Overflow":
                                    item.setForeground(QBrush(QColor("#ffb703")))
                                    continue
                        item.setForeground(QBrush(fg_color))
        finally:
            self.table.itemChanged.connect(self.on_table_item_changed)
            self.table.setUpdatesEnabled(True)
            
        self.table.scrollToItem(self.table.item(row_idx, 0), QAbstractItemView.PositionAtCenter)
        if hasattr(self, "teleprompter_label"):
            self.teleprompter_label.setText(self.segments[row_idx].text)

    def is_system_in_light_mode(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 1
        except Exception:
            return False # Fallback to Dark Mode

    def detect_and_update_theme(self):
        if not self.auto_theme_cb.isChecked():
            return
        current_system_theme = self.is_system_in_light_mode()
        if current_system_theme != self.light_mode:
            self.light_mode = current_system_theme
            self.apply_stylesheet()
            self.rebuild_table_ui()

    def toggle_theme_manually(self):
        self.auto_theme_cb.setChecked(False)
        self.light_mode = not self.light_mode
        self.apply_stylesheet()
        self.rebuild_table_ui()

    def get_theme_stylesheet(self, light_mode):
        if light_mode:
            return """
            QWidget {
                background-color: #f4f4f9;
                color: #1a1a1f;
                font-family: "Segoe UI", "Leelawadee UI", "Noto Sans Khmer", sans-serif;
                font-size: 13px;
            }

            QTabWidget::pane {
                border: 1px solid #d1d1e0;
                background-color: #ffffff;
                border-radius: 8px;
            }

            QTabBar::tab {
                background-color: #f4f4f9;
                color: #666677;
                border: 1px solid #d1d1e0;
                border-bottom: none;
                padding: 10px 18px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-weight: bold;
            }

            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #0077b6;
                border-bottom: 2px solid #0077b6;
            }

            QTabBar::tab:hover:!selected {
                color: #1a1a1f;
                background-color: #e8e8f2;
            }

            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #d1d1e0;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 18px;
                font-weight: bold;
                color: #0077b6;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 15px;
                padding: 0 5px;
                background-color: #f4f4f9;
            }

            QTextEdit, QLineEdit {
                background-color: #ffffff;
                border: 1px solid #d1d1e0;
                border-radius: 6px;
                color: #1a1a1f;
                padding: 8px;
            }

            QTextEdit:focus, QLineEdit:focus {
                border: 1px solid #0077b6;
            }

            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #06B6D4);
                color: #ffffff !important;
                border: 1px solid #60A5FA;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 13px;
            }

            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #0891B2);
                border-color: #93C5FD;
            }

            QPushButton:pressed {
                background-color: #1E40AF;
            }

            QPushButton#secondaryBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F1F5F9, stop:1 #E2E8F0);
                color: #1E293B !important;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
            }

            QPushButton#secondaryBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E2E8F0, stop:1 #CBD5E1);
                border-color: #3B82F6;
                color: #2563EB !important;
            }

            QPushButton#dangerBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DC2626, stop:1 #EF4444);
                color: #ffffff !important;
                border: 1px solid #F87171;
                border-radius: 6px;
            }

            QPushButton#dangerBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B91C1C, stop:1 #DC2626);
            }

            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #d1d1e0;
                gridline-color: #e2e2eb;
                border-radius: 6px;
            }

            QTableWidget::item {
                padding: 6px;
            }

            QHeaderView::section {
                background-color: #e2e2eb;
                color: #2b2d42;
                padding: 8px;
                border: 1px solid #d1d1e0;
                font-weight: bold;
            }

            QSlider::groove:horizontal {
                border: 1px solid #d1d1e0;
                height: 6px;
                background: #e2e2eb;
                border-radius: 3px;
            }

            QSlider::sub-page:horizontal {
                background: #0077b6;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #0077b6;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }

            QSlider::handle:horizontal:hover {
                background: #0077b6;
            }

            QComboBox {
                background-color: #ffffff;
                border: 1px solid #d1d1e0;
                border-radius: 6px;
                color: #1a1a1f;
                padding: 8px;
            }

            QComboBox::drop-down {
                border: none;
            }

            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1a1a1f;
                selection-background-color: #0077b6;
                selection-color: #ffffff;
                border: 1px solid #d1d1e0;
            }

            QProgressBar {
                border: 1px solid #d1d1e0;
                border-radius: 6px;
                text-align: center;
                background-color: #e2e2eb;
                color: #1a1a1f;
                font-weight: bold;
            }

            QProgressBar::chunk {
                background-color: #0077b6;
                border-radius: 5px;
            }

            QScrollBar:vertical {
                border: none;
                background: #f4f4f9;
                width: 10px;
            }

            QScrollBar::handle:vertical {
                background: #d1d1e0;
                min-height: 20px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background: #0077b6;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            
            QCheckBox {
                color: #1a1a1f;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #d1d1e0;
                border-radius: 3px;
                background-color: #ffffff;
            }
            
            QCheckBox::indicator:checked {
                background-color: #0077b6;
                image: url(check_mark.png);
            }

            QLabel#teleprompterLabel {
                background-color: #e2e2eb;
                color: #0077b6;
                border: 1px solid #b5b5c3;
                border-radius: 6px;
                padding: 15px;
                min-height: 80px;
            }
            """
        else:
            return """
            QWidget {
                background-color: #1a1a1f;
                color: #e2e2e9;
                font-family: "Segoe UI", "Leelawadee UI", "Noto Sans Khmer", sans-serif;
                font-size: 13px;
            }

            QTabWidget::pane {
                border: 1px solid #2d2d3d;
                background-color: #21212a;
                border-radius: 8px;
            }

            QTabBar::tab {
                background-color: #1a1a1f;
                color: #88889a;
                border: 1px solid #2d2d3d;
                border-bottom: none;
                padding: 10px 18px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-weight: bold;
            }

            QTabBar::tab:selected {
                background-color: #21212a;
                color: #00b4d8;
                border-bottom: 2px solid #00b4d8;
            }

            QTabBar::tab:hover:!selected {
                color: #f8f9fa;
                background-color: #262633;
            }

            QGroupBox {
                background-color: #21212a;
                border: 1px solid #2d2d3d;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 18px;
                font-weight: bold;
                color: #00b4d8;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 15px;
                padding: 0 5px;
                background-color: #1a1a1f;
            }

            QTextEdit, QLineEdit {
                background-color: #15151c;
                border: 1px solid #2d2d3d;
                border-radius: 6px;
                color: #e2e2e9;
                padding: 8px;
            }

            QTextEdit:focus, QLineEdit:focus {
                border: 1px solid #00b4d8;
            }

            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:0.5 #3B82F6, stop:1 #06B6D4);
                color: #ffffff !important;
                border: 1px solid #60A5FA;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 13px;
            }

            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:0.5 #2563EB, stop:1 #0891B2);
                border-color: #93C5FD;
            }

            QPushButton:pressed {
                background-color: #1E40AF;
            }

            QPushButton#secondaryBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #334155, stop:1 #1E293B);
                color: #F8FAFC !important;
                border: 1px solid #475569;
                border-radius: 6px;
            }

            QPushButton#secondaryBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #475569, stop:1 #334155);
                border-color: #38BDF8;
                color: #38BDF8 !important;
            }

            QPushButton#dangerBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DC2626, stop:1 #EF4444);
                color: #ffffff !important;
                border: 1px solid #F87171;
                border-radius: 6px;
            }

            QPushButton#dangerBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B91C1C, stop:1 #DC2626);
                border-color: #FCA5A5;
            }

            QTableWidget {
                background-color: #15151c;
                border: 1px solid #2d2d3d;
                gridline-color: #252535;
                border-radius: 6px;
            }

            QTableWidget::item {
                padding: 6px;
            }

            QHeaderView::section {
                background-color: #21212a;
                color: #a0a0b0;
                padding: 8px;
                border: 1px solid #2d2d3d;
                font-weight: bold;
            }

            QSlider::groove:horizontal {
                border: 1px solid #2d2d3d;
                height: 6px;
                background: #15151c;
                border-radius: 3px;
            }

            QSlider::sub-page:horizontal {
                background: #00b4d8;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #f8f9fa;
                border: 1px solid #00b4d8;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }

            QSlider::handle:horizontal:hover {
                background: #00b4d8;
            }

            QComboBox {
                background-color: #15151c;
                border: 1px solid #2d2d3d;
                border-radius: 6px;
                color: #e2e2e9;
                padding: 8px;
            }

            QComboBox::drop-down {
                border: none;
            }

            QComboBox QAbstractItemView {
                background-color: #1a1a1f;
                color: #e2e2e9;
                selection-background-color: #00b4d8;
                selection-color: #121214;
                border: 1px solid #2d2d3d;
            }

            QProgressBar {
                border: 1px solid #2d2d3d;
                border-radius: 6px;
                text-align: center;
                background-color: #15151c;
                color: #f8f9fa;
                font-weight: bold;
            }

            QProgressBar::chunk {
                background-color: #00b4d8;
                border-radius: 5px;
            }

            QScrollBar:vertical {
                border: none;
                background: #1a1a1f;
                width: 10px;
            }

            QScrollBar::handle:vertical {
                background: #2d2d3d;
                min-height: 20px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background: #00b4d8;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            
            QCheckBox {
                color: #e2e2e9;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #2d2d3d;
                border-radius: 3px;
                background-color: #15151c;
            }
            
            QCheckBox::indicator:checked {
                background-color: #00b4d8;
                image: url(check_mark.png);
            }

            QLabel#teleprompterLabel {
                background-color: #121214;
                color: #00b4d8;
                border: 1px solid #2f2f4c;
                border-radius: 6px;
                padding: 15px;
                min-height: 80px;
            }
            """

    def apply_stylesheet(self):
        style = self.get_theme_stylesheet(self.light_mode)
        self.setStyleSheet(style)


if __name__ == "__main__":
    if sys.platform == 'win32':
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('khmertts.voiceapp.generator.1.0')
        except Exception:
            pass

    # 144Hz+ High Refresh Rate & Low-Latency GPU Acceleration
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    if hasattr(Qt, 'AA_CompressHighFrequencyEvents'):
        QApplication.setAttribute(Qt.AA_CompressHighFrequencyEvents, False)
    if hasattr(Qt, 'AA_ShareOpenGLContexts'):
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    if hasattr(Qt, 'AA_UseOpenGLES'):
        QApplication.setAttribute(Qt.AA_UseOpenGLES, True)

    app = QApplication(sys.argv)
    
    # Locate icon file (PL Khmer Voice.ico, PL_TTS_Voice.ico, icon.ico or icon-ico)
    icon_file = "PL Khmer Voice.ico"
    if not os.path.exists(icon_file):
        icon_file = "PL_TTS_Voice.ico"
    if not os.path.exists(icon_file):
        icon_file = "icon.ico"
    if not os.path.exists(icon_file):
        icon_file = "icon-ico"
    if getattr(sys, 'frozen', False):
        bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        for name in ["PL Khmer Voice.ico", "PL_TTS_Voice.ico", "icon.ico", "icon-ico"]:
            p = os.path.join(bundle_dir, name)
            if os.path.exists(p):
                icon_file = p
                break

    if os.path.exists(icon_file):
        app_icon = QIcon(icon_file)
        app.setWindowIcon(app_icon)

    window = KhmerTTSApp()
    if os.path.exists(icon_file):
        window.setWindowIcon(QIcon(icon_file))
    window.show()
    sys.exit(app.exec_())
