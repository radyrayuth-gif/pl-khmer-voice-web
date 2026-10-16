import os
import sys
import json
import time
import asyncio
import re
import gc
import traceback
from typing import List, Dict, Any, Optional
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure SRT directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRT_DIR = os.path.join(BASE_DIR, "SRT")
if SRT_DIR not in sys.path:
    sys.path.insert(0, SRT_DIR)

AUDIO_OUTPUT_DIR = os.path.join(BASE_DIR, "audio_output")
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)

# Detect if running in cloud container (Render, Hugging Face, etc.)
IS_CLOUD = bool(os.environ.get("RENDER") or os.environ.get("PORT") or os.environ.get("SPACE_ID"))
# On cloud free tier (Render 0.1 CPU, 512MB RAM), optimized 128k bitrate allows smooth 6-worker concurrency
DEFAULT_TTS_CONCURRENCY = 6 if IS_CLOUD else 12
DEFAULT_BATCH_CONCURRENCY = 3 if IS_CLOUD else 6

def clean_old_temp_audio_files(max_age_sec: int = 7200):
    """Deletes temporary line_*.mp3 and master_*.mp3 files older than 2 hours to prevent disk exhaustion."""
    try:
        now = time.time()
        for fname in os.listdir(AUDIO_OUTPUT_DIR):
            if fname.startswith("line_") or fname.startswith("master_"):
                fpath = os.path.join(AUDIO_OUTPUT_DIR, fname)
                try:
                    if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > max_age_sec:
                        os.remove(fpath)
                except Exception:
                    pass
    except Exception as e:
        print(f"[Cleanup] Old audio files cleanup warning: {e}")

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
import edge_tts
from pydub import AudioSegment
import srt

# Import audio processing helpers (pure Python + pydub, zero PyQt5 dependency)
try:
    from voice_helpers import (
        apply_echo_effect,
        clean_tts_text,
        expand_khmer_lekh_tho,
        get_file_duration_ms,
        parse_voice_and_echo_from_text,
        trim_leading_trailing_silence,
    )
except ImportError:
    from voice_engine import (
        apply_echo_effect,
        clean_tts_text,
        expand_khmer_lekh_tho,
        get_file_duration_ms,
        parse_voice_and_echo_from_text,
        trim_leading_trailing_silence,
    )

# Import subtitle translation engine
try:
    from translator_engine import (
        GeminiSubtitleTranslator,
        detect_and_read_file,
        export_srt_file,
        format_timestamp,
        is_promo_ad_line,
        normalize_gemini_model,
        number_to_khmer_words,
        parse_srt_content,
        replace_numbers_with_khmer_words,
        sanitize_khmer_text,
        test_gemini_api_key,
    )
except ImportError:
    from SRT.translator_engine import (
        GeminiSubtitleTranslator,
        detect_and_read_file,
        export_srt_file,
        format_timestamp,
        is_promo_ad_line,
        normalize_gemini_model,
        number_to_khmer_words,
        parse_srt_content,
        replace_numbers_with_khmer_words,
        sanitize_khmer_text,
        test_gemini_api_key,
    )

app = FastAPI(title="PL Khmer Voice - SRT & TTS Studio", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.exists(os.path.join(STATIC_DIR, "index.html")) and os.path.exists(os.path.join(BASE_DIR, "index.html")):
    STATIC_DIR = BASE_DIR
os.makedirs(STATIC_DIR, exist_ok=True)

# Helper to read desktop settings from QSettings
def get_desktop_settings() -> Dict[str, Any]:
    settings_data = {
        "api_keys": [],
        "gemini_model": "gemini-3.5-flash-lite",
        "style": "emotion_acting",
        "default_voice": "km-KH-PisethNeural",
        "default_female_voice": "km-KH-SreymomNeural",
        "batch_size": 30,
        "concurrency": 8,
        "request_delay": 0.1,
        "rate": "+20%",
        "pitch": "+0Hz",
        "bitrate": "128k"
    }
    try:
        from PyQt5.QtCore import QSettings
        qs = QSettings("GeminiTranslatorApp", "ChineseToKhmerSRT")
        raw_key = str(qs.value("gemini_api_key", "") or "").strip()
        history = qs.value("gemini_api_keys_history", [])
        keys = []
        if raw_key and "..." not in raw_key:
            keys.append(raw_key)
        if isinstance(history, list):
            for k in history:
                k_clean = str(k).strip()
                if k_clean and "..." not in k_clean and k_clean not in keys:
                    keys.append(k_clean)
        if keys:
            settings_data["api_keys"] = keys
        
        saved_model = qs.value("gemini_model")
        if saved_model:
            settings_data["gemini_model"] = normalize_gemini_model(str(saved_model))
            
        saved_style = qs.value("translation_style")
        if saved_style:
            settings_data["style"] = str(saved_style)

        saved_batch = qs.value("batch_size")
        if saved_batch:
            settings_data["batch_size"] = int(saved_batch)

        saved_threads = qs.value("concurrent_batches")
        if saved_threads:
            settings_data["concurrency"] = int(saved_threads)

        saved_delay = qs.value("request_delay")
        if saved_delay:
            settings_data["request_delay"] = float(saved_delay)

        saved_speed = qs.value("tts_speed_slider")
        if saved_speed is not None:
            try:
                spd = int(saved_speed)
                settings_data["rate"] = f"{spd:+d}%"
            except Exception:
                pass
    except Exception as e:
        print(f"[Settings] QSettings read note: {e}")
    return settings_data

# WebSocket Manager for Real-time Progress Broadcasting
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# Global execution state
cancel_requested = False
is_pipeline_running = False

# Pydantic Request Models
class TestKeyReq(BaseModel):
    api_key: str
    model_name: Optional[str] = "gemini-3.5-flash-lite"

class SaveSettingsReq(BaseModel):
    api_keys: List[str]
    gemini_model: Optional[str] = "gemini-3.5-flash-lite"
    style: Optional[str] = "emotion_acting"
    batch_size: Optional[int] = 30
    concurrency: Optional[int] = 8
    request_delay: Optional[float] = 0.1
    rate: Optional[str] = "+20%"
    pitch: Optional[str] = "+0Hz"
    bitrate: Optional[str] = "128k"

class AutoPipelineReq(BaseModel):
    items: List[Dict[str, Any]]
    api_keys: List[str]
    model_name: Optional[str] = "gemini-3.5-flash-lite"
    style: Optional[str] = "emotion_acting"
    batch_size: Optional[int] = 30
    concurrency: Optional[int] = 8
    request_delay: Optional[float] = 0.1
    rate: Optional[str] = "+20%"
    pitch: Optional[str] = "+0Hz"
    auto_speed: Optional[bool] = True
    bitrate: Optional[str] = "128k"
    filename: Optional[str] = "master_voiceover.srt"

class GenAllVoicesReq(BaseModel):
    items: List[Dict[str, Any]]
    rate: Optional[str] = "+20%"
    pitch: Optional[str] = "+0Hz"
    bitrate: Optional[str] = "128k"
    filename: Optional[str] = "master_voiceover.srt"

class SingleTTSReq(BaseModel):
    id: int
    text: str
    voice: Optional[str] = "Auto"
    gender: Optional[str] = "ប្រុស"
    echo: Optional[str] = "No"
    speed: Optional[str] = "Default"
    target_ms: Optional[int] = 2000
    rate: Optional[str] = "+20%"
    pitch: Optional[str] = "+0Hz"

class CompileMasterReq(BaseModel):
    items: List[Dict[str, Any]]
    filename: Optional[str] = "master_voiceover.mp3"
    bitrate: Optional[str] = "128k"

class ExportMasterReq(BaseModel):
    items: List[Dict[str, Any]]
    include_gender_tag: Optional[bool] = True
    bitrate: Optional[str] = "128k"
    filename: Optional[str] = None

# Helper for resolving voice name
def resolve_voice_name(voice_setting: str, gender: str, default_voice: str = "km-KH-PisethNeural") -> str:
    if voice_setting == "Sreymom" or voice_setting == "km-KH-SreymomNeural":
        return "km-KH-SreymomNeural"
    if voice_setting == "Piseth" or voice_setting == "km-KH-PisethNeural":
        return "km-KH-PisethNeural"
    # Auto
    return "km-KH-SreymomNeural" if gender == "ស្រី" else "km-KH-PisethNeural"

# Generate Single Line Audio helper with Echo & Auto-Speed matching voice_engine.py
async def generate_single_audio_clip(
    sub_id: int,
    text: str,
    target_ms: int,
    voice_setting: str,
    gender: str,
    echo_setting: str,
    speed_setting: str,
    global_rate: str = "+20%",
    global_pitch: str = "+0Hz",
    bitrate: str = "128k"
) -> Dict[str, Any]:
    # 1. Clean TTS text with Lekh Tho expansion (matching voice_engine.py)
    clean_text = clean_tts_text(text)
    clean_text = sanitize_khmer_text(clean_text)

    # 2. Check detected voice/echo in text if setting is Auto
    det_voice, det_echo = parse_voice_and_echo_from_text(text)
    if voice_setting == "Auto":
        if det_voice == "Sreymom":
            resolved_voice = "km-KH-SreymomNeural"
        elif det_voice == "Piseth":
            resolved_voice = "km-KH-PisethNeural"
        else:
            resolved_voice = "km-KH-SreymomNeural" if gender == "ស្រី" else "km-KH-PisethNeural"
    else:
        resolved_voice = resolve_voice_name(voice_setting, gender)

    # 3. Echo resolution
    if echo_setting == "Auto":
        use_echo = det_echo
    elif echo_setting == "Yes":
        use_echo = True
    else:
        use_echo = False

    # 4. Calibrated 1-Pass Speech Rate Calculation based on Khmer Edge-TTS phonetics
    rate_to_use = global_rate or "+20%"
    if (speed_setting == "Auto" or speed_setting.startswith("Auto")) and target_ms > 0:
        char_count = len(clean_text)
        safe_target_sec = max(0.4, (target_ms * 0.90) / 1000.0)
        est_sec = char_count / 9.5
        base_rate_pct = 20
        try:
            m_rate = re.search(r'([+-]?\d+)', str(global_rate or ""))
            if m_rate:
                base_rate_pct = int(m_rate.group(1))
        except Exception:
            base_rate_pct = 20
        if est_sec > safe_target_sec:
            calc_pct = int(((est_sec / safe_target_sec) - 1.0) * 100)
            final_pct = max(base_rate_pct, min(90, calc_pct))
            rate_to_use = f"{final_pct:+d}%"
        else:
            rate_to_use = f"{base_rate_pct:+d}%"
    elif speed_setting != "Default" and speed_setting != "Auto":
        rate_to_use = speed_setting

    filename = f"line_{sub_id:03d}_{int(time.time() * 1000)}.mp3"
    filepath = os.path.join(AUDIO_OUTPUT_DIR, filename)

    # 5. Check speakable content
    has_content = bool(re.search(r'[\u1780-\u17FFa-zA-Z0-9]', clean_text))
    export_params = ["-ar", "44100"]
    if not has_content:
        silence_dur = max(200, min(target_ms, 5000)) if target_ms > 0 else 500
        silent = AudioSegment.silent(duration=silence_dur, frame_rate=44100)
        silent.export(filepath, format="mp3", bitrate=bitrate or "128k", parameters=export_params)
        return {
            "id": sub_id,
            "audio_url": f"/audio_output/{filename}",
            "duration_ms": silence_dur,
            "filepath": filepath,
            "rate_used": rate_to_use
        }

    # Generate with Edge-TTS
    comm = edge_tts.Communicate(text=clean_text, voice=resolved_voice, rate=rate_to_use, pitch=global_pitch)
    await comm.save(filepath)

    # Trim leading/trailing silence to guarantee exact timestamp sync
    if os.path.exists(filepath):
        try:
            raw_audio = AudioSegment.from_file(filepath)
            trimmed = trim_leading_trailing_silence(raw_audio)
            
            # Apply Echo effect if line has echo
            if use_echo:
                trimmed = apply_echo_effect(trimmed)

            trimmed.export(filepath, format="mp3", bitrate=bitrate or "128k", parameters=export_params)
        except Exception as e:
            print(f"Audio postprocessing warning for line {sub_id}: {e}")

    dur_ms = get_file_duration_ms(filepath)
    return {
        "id": sub_id,
        "audio_url": f"/audio_output/{filename}",
        "duration_ms": dur_ms,
        "filepath": filepath,
        "rate_used": rate_to_use
    }

# Helper to compile Master MP3
def compile_master_audio_file(items: List[Dict[str, Any]], out_filename: Optional[str] = None, bitrate: str = "128k") -> Optional[Dict[str, Any]]:
    valid_clips = []
    for it in items:
        audio_url = it.get("audio_url")
        if not audio_url:
            continue
        filename = os.path.basename(audio_url)
        filepath = os.path.join(AUDIO_OUTPUT_DIR, filename)
        if os.path.exists(filepath):
            start_ms = it.get("start_ms", 0)
            end_ms = it.get("end_ms", start_ms + 1000)
            dur_ms = it.get("duration_ms", end_ms - start_ms)
            valid_clips.append((filepath, start_ms, end_ms, dur_ms))

    if not valid_clips:
        return None

    if out_filename:
        # Clean extension and force .mp3 exactly matching the original file name
        base_clean = re.sub(r'\.[^.]+$', '', out_filename).strip()
        final_mp3_name = f"{base_clean}.mp3" if base_clean else f"master_{int(time.time())}.mp3"
    else:
        final_mp3_name = f"master_{int(time.time())}.mp3"

    out_filepath = os.path.join(AUDIO_OUTPUT_DIR, final_mp3_name)

    # Sort clips chronologically by start timestamp
    valid_clips.sort(key=lambda x: x[1])

    # Ultra-low-memory sequential timeline assembler (avoids OOM on 512MB RAM)
    master = AudioSegment.empty()
    cur_pos = 0

    for path, start_ms, end_ms, dur_ms in valid_clips:
        try:
            clip = AudioSegment.from_file(path)
            clip_len = len(clip)

            if start_ms > cur_pos:
                gap = start_ms - cur_pos
                master += AudioSegment.silent(duration=gap, frame_rate=44100)
                master += clip
                cur_pos = start_ms + clip_len
            elif start_ms < cur_pos:
                # Small overlap: overlay clip at offset start_ms
                master = master.overlay(clip, position=start_ms)
                cur_pos = max(cur_pos, start_ms + clip_len)
            else:
                master += clip
                cur_pos += clip_len
        except Exception as e:
            print(f"Overlay error for {path}: {e}")

    max_dur = max(cur_pos, 1000)
    if len(master) == 0:
        master = AudioSegment.silent(duration=1000, frame_rate=44100)

    export_params = ["-ar", "44100"]
    master.export(out_filepath, format="mp3", bitrate=bitrate or "128k", parameters=export_params)
    del master
    clean_old_temp_audio_files()
    gc.collect()

    return {
        "master_url": f"/audio_output/{final_mp3_name}",
        "filename": final_mp3_name,
        "filepath": out_filepath,
        "duration_ms": max_dur,
        "duration_sec": round(max_dur / 1000.0, 2)
    }

# =====================================================================
# API Endpoints
# =====================================================================

@app.get("/api/settings")
def api_get_settings():
    return get_desktop_settings()

@app.post("/api/test-key")
def api_test_key(req: TestKeyReq):
    is_valid, msg = test_gemini_api_key(req.api_key, req.model_name or "gemini-3.5-flash-lite")
    return {"valid": is_valid, "message": msg}

@app.post("/api/parse-srt")
async def api_parse_srt(file: UploadFile = File(...)):
    """Parse SRT into structured 9-column items exactly matching desktop app."""
    try:
        content_bytes = await file.read()
        encodings = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'big5', 'utf-16', 'cp936']
        content = None
        for enc in encodings:
            try:
                content = content_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if content is None:
            content = content_bytes.decode('utf-8', errors='replace')

        subtitles = parse_srt_content(content)
        items = []
        for sub in subtitles:
            sid = sub.index
            start_tc = format_timestamp(sub.start)
            end_tc = format_timestamp(sub.end)
            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            target_ms = max(500, end_ms - start_ms)
            clean_text = sub.content.strip()

            # Parse voice and echo tags
            detected_voice, has_echo = parse_voice_and_echo_from_text(clean_text)
            clean_display_text = re.sub(r"^\[[^\]]*\]\s*", "", clean_text)
            
            gender = "ស្រី" if detected_voice == "Sreymom" else "ប្រុស"
            voice = detected_voice if detected_voice in ["Sreymom", "Piseth"] else "Auto"
            echo = "Yes" if has_echo else "No"

            items.append({
                "id": sid,
                "time_str": f"{start_tc} --> {end_tc}",
                "start": start_tc,
                "end": end_tc,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "target_ms": target_ms,
                "voice": voice,
                "gender": gender,
                "echo": echo,
                "orig_text": clean_display_text,
                "khmer_text": "",
                "speed": "Auto",
                "duration_str": f"- / {(target_ms / 1000.0):.1f}s",
                "duration_ms": 0,
                "status": "រង់ចាំ",
                "audio_url": None
            })

        return {"success": True, "count": len(items), "items": items, "filename": file.filename}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"កំហុសក្នុងការអានឯកសារ SRT: {str(e)}")

@app.get("/api/sample-srt")
def api_sample_srt():
    """Load default sample_chinese.srt with exact 9-column format."""
    sample_path = os.path.join(SRT_DIR, "sample_chinese.srt")
    progress_path = os.path.join(SRT_DIR, "sample_chinese.progress.json")
    
    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail="រកមិនឃើញ sample_chinese.srt")

    with open(sample_path, "r", encoding="utf-8") as f:
        content = f.read()
    subtitles = parse_srt_content(content)
    
    progress_data = {}
    if os.path.exists(progress_path):
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                progress_data = json.load(f)
        except Exception:
            pass

    items = []
    for sub in subtitles:
        sid = sub.index
        start_tc = format_timestamp(sub.start)
        end_tc = format_timestamp(sub.end)
        start_ms = int(sub.start.total_seconds() * 1000)
        end_ms = int(sub.end.total_seconds() * 1000)
        target_ms = max(500, end_ms - start_ms)
        clean_text = sub.content.strip()

        prog = progress_data.get(str(sid), {})
        khmer = prog.get("khmer", "")
        gender = prog.get("gender", "ប្រុស")
        voice = "Sreymom" if gender == "ស្រី" else "Piseth"

        items.append({
            "id": sid,
            "time_str": f"{start_tc} --> {end_tc}",
            "start": start_tc,
            "end": end_tc,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "target_ms": target_ms,
            "voice": voice,
            "gender": gender,
            "echo": "No",
            "orig_text": clean_text,
            "khmer_text": khmer,
            "speed": "Auto",
            "duration_str": f"- / {(target_ms / 1000.0):.1f}s",
            "duration_ms": 0,
            "status": "បកប្រែរួច" if khmer else "រង់ចាំ",
            "audio_url": None
        })

    return {"success": True, "count": len(items), "items": items, "filename": "sample_chinese.srt"}

# =====================================================================
# 1-CLICK MASTER AUTO PIPELINE (Exact Workflow of main.py)
# =====================================================================
@app.post("/api/auto-start")
async def api_auto_start(req: AutoPipelineReq):
    """
    1-Click Master Auto Start Pipeline:
    Stage 1: AI Gender & Character Diarization
    Stage 2: Turbo Multi-threaded Translation with Gemini
    Stage 3: Simultaneous Real-time Streaming TTS Dubbing
    """
    global cancel_requested, is_pipeline_running
    cancel_requested = False
    is_pipeline_running = True

    if not req.api_keys:
        raise HTTPException(status_code=400, detail="សូមបញ្ចូល Gemini API Key យ៉ាងហោចណាស់មួយ។")
    if not req.items:
        raise HTTPException(status_code=400, detail="គ្មានទិន្នន័យ Subtitle ឡើយ។")

    async def execute_auto_pipeline():
        global cancel_requested, is_pipeline_running
        try:
            total_items = len(req.items)
            items_dict = {it["id"]: dict(it) for it in req.items}
            
            # --- STAGE 1: Global Character Casting & Diarization ---
            await manager.broadcast({
                "type": "pipeline_status",
                "stage": "diarization",
                "message": "🎭 [Stage 1/3] កំពុងវិភាគតួអង្គ និងបែងចែកភេទ (Gender Diarization)...",
                "progress": 5
            })

            translator = GeminiSubtitleTranslator(
                api_keys=req.api_keys,
                model_name=req.model_name or "gemini-3.5-flash-lite",
                style=req.style or "emotion_acting"
            )

            # Sample items for global character roster
            loop = asyncio.get_event_loop()
            items_for_cast = [{"id": it["id"], "text": it["orig_text"]} for it in req.items]
            roster = await loop.run_in_executor(None, lambda: translator.extract_global_character_roster(items_for_cast))
            translator.global_character_roster = roster

            if cancel_requested:
                await manager.broadcast({"type": "pipeline_status", "stage": "stopped", "message": "🛑 បានបញ្ឈប់ដំណើរការ។", "progress": 0})
                return

            # Analyze full script genders
            def on_gender_chunk(chunk_dict, cur_done, total_count):
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast({
                        "type": "gender_update",
                        "genders": chunk_dict,
                        "cur_done": cur_done,
                        "total": total_count,
                        "message": f"⚡ វិភាគ Speaker & ភេទ បាន {cur_done}/{total_count} បន្ទាត់"
                    }),
                    loop
                )

            gender_map = await loop.run_in_executor(
                None,
                lambda: translator.analyze_full_script_genders(
                    items=items_for_cast,
                    concurrency=req.concurrency or 8,
                    chunk_size=120,
                    chunk_callback=on_gender_chunk
                )
            )

            # Broadcast gender updates
            for sid, g in gender_map.items():
                if sid in items_dict:
                    items_dict[sid]["gender"] = g
                    if items_dict[sid]["voice"] == "Auto":
                        items_dict[sid]["voice"] = "Sreymom" if g == "ស្រី" else "Piseth"
                    await manager.broadcast({
                        "type": "row_updated",
                        "id": sid,
                        "gender": g,
                        "voice": items_dict[sid]["voice"],
                        "status": "វិភាគរួច"
                    })

            if cancel_requested:
                await manager.broadcast({"type": "pipeline_status", "stage": "stopped", "message": "🛑 បានបញ្ឈប់ដំណើរការ។", "progress": 0})
                return

            # --- STAGE 2 & 3: Turbo Batch Translation & Live Streaming TTS Dubbing ---
            await manager.broadcast({
                "type": "pipeline_status",
                "stage": "translating_and_dubbing",
                "message": f"⚡ [Stage 2 & 3] កំពុងបកប្រែ និងបង្កើតសំឡេង (Turbo Streaming Mode)...",
                "progress": 25
            })

            pending_items = []
            for it in req.items:
                sid = it["id"]
                dur = (it.get("target_ms", 2000) / 1000.0)
                clean_orig = it.get("orig_text", "").strip()
                if not is_promo_ad_line(clean_orig, ""):
                    pending_items.append({
                        "id": sid,
                        "text": clean_orig,
                        "duration_sec": dur,
                        "max_speech_sec": round(dur * 1.7, 2)
                    })

            batch_size = req.batch_size or 30
            batches_with_ctx = []
            for i in range(0, len(pending_items), batch_size):
                b = pending_items[i : i + batch_size]
                prec = pending_items[max(0, i - 6) : i] if i > 0 else []
                batches_with_ctx.append((b, prec))

            total_batches = len(batches_with_ctx)
            completed_count = 0

            # Concurrency workers: dynamic scaling based on cloud vs local environment
            tts_concurrency = DEFAULT_TTS_CONCURRENCY if IS_CLOUD else min(req.concurrency or 8, 12)
            batch_concurrency = DEFAULT_BATCH_CONCURRENCY if IS_CLOUD else min(req.concurrency or 6, 8)
            tts_semaphore = asyncio.Semaphore(tts_concurrency)
            batch_semaphore = asyncio.Semaphore(batch_concurrency)
            tts_tasks = []

            async def process_batch_and_stream_tts(batch_tuple, b_idx):
                nonlocal completed_count
                if cancel_requested:
                    return

                async with batch_semaphore:
                    if cancel_requested:
                        return
                    b_data, prec_ctx = batch_tuple
                    
                    # Run batch translation
                    batch_res = await loop.run_in_executor(
                        None,
                        lambda: translator.translate_batch(
                            b_data,
                            gender_hints=gender_map,
                            preceding_context=prec_ctx
                        )
                    )

                    if cancel_requested:
                        return

                    # Send batch translations
                    for item_id, item_info in batch_res.items():
                        km_text = item_info.get("khmer", "")
                        items_dict[item_id]["khmer_text"] = km_text
                        await manager.broadcast({
                            "type": "row_updated",
                            "id": item_id,
                            "khmer_text": km_text,
                            "status": "បកប្រែរួច"
                        })

                        # Live Streaming TTS Dubbing with 16 concurrent workers
                        async def synthesize_row(iid, txt):
                            if cancel_requested or not txt.strip():
                                return
                            async with tts_semaphore:
                                row_item = items_dict.get(iid, {})
                                target_ms = row_item.get("target_ms", 2000)
                                voice = row_item.get("voice", "Auto")
                                gender = row_item.get("gender", "ប្រុស")
                                echo = row_item.get("echo", "No")
                                speed = row_item.get("speed", "Auto")
                                
                                try:
                                    clip_res = await generate_single_audio_clip(
                                        sub_id=iid,
                                        text=txt,
                                        target_ms=target_ms,
                                        voice_setting=voice,
                                        gender=gender,
                                        echo_setting=echo,
                                        speed_setting=speed,
                                        global_rate=req.rate or "+20%",
                                        global_pitch=req.pitch or "+0Hz",
                                        bitrate=req.bitrate or "128k"
                                    )
                                    dur_sec = clip_res["duration_ms"] / 1000.0
                                    dur_str = f"{dur_sec:.1f}s / {(target_ms / 1000.0):.1f}s"
                                    items_dict[iid]["audio_url"] = clip_res["audio_url"]
                                    items_dict[iid]["duration_ms"] = clip_res["duration_ms"]
                                    items_dict[iid]["duration_str"] = dur_str
                                    items_dict[iid]["speed"] = clip_res.get("rate_used", "Auto")
                                    items_dict[iid]["status"] = "សំឡេងរួចរាល់"
                                    
                                    await manager.broadcast({
                                        "type": "row_updated",
                                        "id": iid,
                                        "audio_url": clip_res["audio_url"],
                                        "duration_ms": clip_res["duration_ms"],
                                        "duration_str": dur_str,
                                        "speed": clip_res.get("rate_used", "Auto"),
                                        "status": "សំឡេងរួចរាល់"
                                    })
                                except Exception as err:
                                    print(f"Streaming TTS error for row {iid}: {err}")

                        task = asyncio.create_task(synthesize_row(item_id, km_text))
                        tts_tasks.append(task)

                    completed_count += len(b_data)
                    pct = int(25 + (completed_count / total_items) * 65)
                    await manager.broadcast({
                        "type": "pipeline_status",
                        "stage": "translating_and_dubbing",
                        "message": f"⚡ បានបកប្រែ {completed_count}/{total_items} ជួរ ({pct}%)...",
                        "progress": pct
                    })

            # Run batches concurrently using batch_semaphore
            batch_tasks = [asyncio.create_task(process_batch_and_stream_tts(bt, idx)) for idx, bt in enumerate(batches_with_ctx)]
            await asyncio.gather(*batch_tasks)

            # Wait for all streaming TTS tasks to finish
            if tts_tasks:
                await manager.broadcast({
                    "type": "pipeline_status",
                    "stage": "finishing_tts",
                    "message": "🎙️ កំពុងបញ្ចប់ការបង្កើតសំឡេងទាំងអស់...",
                    "progress": 92
                })
                await asyncio.gather(*tts_tasks, return_exceptions=True)

            if cancel_requested:
                await manager.broadcast({"type": "pipeline_status", "stage": "stopped", "message": "🛑 ដំណើរការត្រូវបានផ្អាក", "progress": 0})
                return

            # Automatically compile Master Voiceover MP3 matching original file name
            await manager.broadcast({
                "type": "pipeline_status",
                "stage": "compiling_master",
                "message": "🎵 [Stage 4/4] កំពុង Export និងផ្គុំ Master Audio MP3 ដោយស្វ័យប្រវត្តិ...",
                "progress": 96
            })

            master_res = await loop.run_in_executor(None, lambda: compile_master_audio_file(list(items_dict.values()), out_filename=req.filename, bitrate=req.bitrate or "128k"))

            master_url = master_res["master_url"] if master_res else None
            master_dur = master_res["duration_sec"] if master_res else 0
            master_fn = master_res["filename"] if master_res else "master_voiceover.mp3"

            msg = f"🎉 ដំណើរការ Auto Start ទាំងស្រុងបានបញ្ចប់ និង Export Master MP3 រួចរាល់ ({master_dur}s)!"
            await manager.broadcast({
                "type": "pipeline_status",
                "stage": "completed",
                "message": msg,
                "master_url": master_url,
                "master_filename": master_fn,
                "progress": 100
            })

        except Exception as e:
            traceback.print_exc()
            await manager.broadcast({
                "type": "pipeline_status",
                "stage": "error",
                "message": f"❌ កំហុសក្នុង Auto Pipeline: {str(e)}",
                "progress": 0
            })
        finally:
            is_pipeline_running = False

    asyncio.create_task(execute_auto_pipeline())
    return {"status": "started", "message": "Auto Pipeline Started"}

@app.post("/api/cancel-operation")
def api_cancel_operation():
    global cancel_requested, is_pipeline_running
    cancel_requested = True
    is_pipeline_running = False
    return {"success": True, "message": "បានផ្ញើសញ្ញាបញ្ឈប់"}

@app.post("/api/tts-single-row")
async def api_tts_single_row(req: SingleTTSReq):
    """Generate TTS for a single row with Echo & Speed calculation."""
    try:
        clip_res = await generate_single_audio_clip(
            sub_id=req.id,
            text=req.text,
            target_ms=req.target_ms or 2000,
            voice_setting=req.voice or "Auto",
            gender=req.gender or "ប្រុស",
            echo_setting=req.echo or "No",
            speed_setting=req.speed or "Default",
            global_rate=req.rate or "+20%",
            global_pitch=req.pitch or "+0Hz"
        )
        return {
            "success": True,
            "id": req.id,
            "audio_url": clip_res["audio_url"],
            "duration_ms": clip_res["duration_ms"],
            "duration_str": f"{(clip_res['duration_ms'] / 1000.0):.1f}s / {((req.target_ms or 2000) / 1000.0):.1f}s",
            "rate_used": clip_res["rate_used"]
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/gen-all-voices")
async def api_gen_all_voices(req: GenAllVoicesReq):
    """Generate audio for all rows concurrently (up to 16 threads) and auto-compile master MP3."""
    global cancel_requested, is_pipeline_running
    cancel_requested = False
    is_pipeline_running = True

    if not req.items:
        raise HTTPException(status_code=400, detail="គ្មានទិន្នន័យ Subtitle ឡើយ។")

    async def execute_gen_all():
        global cancel_requested, is_pipeline_running
        try:
            total_items = len(req.items)
            items_dict = {it["id"]: dict(it) for it in req.items}
            concurrency_val = DEFAULT_TTS_CONCURRENCY if IS_CLOUD else 12
            sem = asyncio.Semaphore(concurrency_val)
            completed_tts = 0

            await manager.broadcast({
                "type": "pipeline_status",
                "stage": "translating_and_dubbing",
                "message": f"🎙️ កំពុងបង្កើតសំឡេងទាំងអស់ដោយល្បឿនលឿន ({concurrency_val} Workers)...",
                "progress": 5
            })

            async def gen_item(it):
                nonlocal completed_tts
                if cancel_requested:
                    return
                iid = it["id"]
                txt = (it.get("khmer_text") or it.get("orig_text") or "").strip()
                if not txt:
                    return

                async with sem:
                    if cancel_requested:
                        return
                    target_ms = it.get("target_ms", 2000)
                    voice = it.get("voice", "Auto")
                    gender = it.get("gender", "ប្រុស")
                    echo = it.get("echo", "No")
                    speed = it.get("speed", "Auto")

                    try:
                        clip_res = await generate_single_audio_clip(
                            sub_id=iid,
                            text=txt,
                            target_ms=target_ms,
                            voice_setting=voice,
                            gender=gender,
                            echo_setting=echo,
                            speed_setting=speed,
                            global_rate=req.rate or "+20%",
                            global_pitch=req.pitch or "+0Hz",
                            bitrate=req.bitrate or "128k"
                        )
                        dur_sec = clip_res["duration_ms"] / 1000.0
                        dur_str = f"{dur_sec:.1f}s / {(target_ms / 1000.0):.1f}s"
                        items_dict[iid]["audio_url"] = clip_res["audio_url"]
                        items_dict[iid]["duration_ms"] = clip_res["duration_ms"]
                        items_dict[iid]["duration_str"] = dur_str
                        items_dict[iid]["speed"] = clip_res.get("rate_used", "Auto")
                        items_dict[iid]["status"] = "សំឡេងរួចរាល់"

                        completed_tts += 1
                        pct = int((completed_tts / total_items) * 88)
                        await manager.broadcast({
                            "type": "row_updated",
                            "id": iid,
                            "audio_url": clip_res["audio_url"],
                            "duration_ms": clip_res["duration_ms"],
                            "duration_str": dur_str,
                            "speed": clip_res.get("rate_used", "Auto"),
                            "status": "សំឡេងរួចរាល់"
                        })
                        await manager.broadcast({
                            "type": "pipeline_status",
                            "stage": "translating_and_dubbing",
                            "message": f"🎙️ បានបង្កើតសំឡេង {completed_tts}/{total_items} ជួរ ({pct}%)...",
                            "progress": pct
                        })
                    except Exception as err:
                        print(f"Gen all voices error for row {iid}: {err}")

            tasks = [asyncio.create_task(gen_item(it)) for it in req.items]
            await asyncio.gather(*tasks, return_exceptions=True)

            if cancel_requested:
                await manager.broadcast({"type": "pipeline_status", "stage": "stopped", "message": "🛑 បានបញ្ឈប់ដំណើរការ។", "progress": 0})
                return

            # Auto compile master MP3 matching original filename
            await manager.broadcast({
                "type": "pipeline_status",
                "stage": "compiling_master",
                "message": "🎵 កំពុង Export និងផ្គុំ Master Audio MP3 ដោយស្វ័យប្រវត្តិ...",
                "progress": 94
            })

            loop = asyncio.get_event_loop()
            master_res = await loop.run_in_executor(None, lambda: compile_master_audio_file(list(items_dict.values()), out_filename=req.filename, bitrate=req.bitrate or "128k"))

            master_url = master_res["master_url"] if master_res else None
            master_dur = master_res["duration_sec"] if master_res else 0
            master_fn = master_res["filename"] if master_res else "master_voiceover.mp3"

            await manager.broadcast({
                "type": "pipeline_status",
                "stage": "completed",
                "message": f"🎉 បង្កើតសំឡេងទាំងអស់ និង Export Master MP3 រួចរាល់ ({master_dur}s)!",
                "master_url": master_url,
                "master_filename": master_fn,
                "progress": 100
            })
        except Exception as e:
            traceback.print_exc()
            await manager.broadcast({
                "type": "pipeline_status",
                "stage": "error",
                "message": f"❌ កំហុសក្នុងការបង្កើតសំឡេង: {str(e)}",
                "progress": 0
            })
        finally:
            is_pipeline_running = False

    asyncio.create_task(execute_gen_all())
    return {"status": "started", "message": "Voice generation started"}

@app.post("/api/compile-master")
async def api_compile_master(req: CompileMasterReq):
    """Compile master audio using compile_master_audio_file helper."""
    items = req.items
    if not items:
        raise HTTPException(status_code=400, detail="គ្មានទិន្នន័យសំឡេងត្រូវផ្គុំឡើយ")

    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, lambda: compile_master_audio_file(items, req.filename, req.bitrate or "128k"))
    if not res:
        raise HTTPException(status_code=400, detail="មិនទាន់មានសំឡេងណាមួយត្រូវបានបង្កើតឡើយ។")

    return {
        "success": True,
        "master_url": res["master_url"],
        "filename": res["filename"],
        "duration_ms": res["duration_ms"],
        "duration_sec": res["duration_sec"]
    }

@app.post("/api/export-master")
async def api_export_master(req: ExportMasterReq):
    """2-in-1 Export: Compiles Master MP3 and exports translated SRT."""
    items = req.items
    if not items:
        raise HTTPException(status_code=400, detail="គ្មានទិន្នន័យត្រូវនាំចេញឡើយ។")

    # 1. Generate SRT content
    sub_objects = []
    for it in items:
        sid = it["id"]
        start_td = timedelta(milliseconds=it.get("start_ms", 0))
        end_td = timedelta(milliseconds=it.get("end_ms", 1000))
        khmer_txt = (it.get("khmer_text") or it.get("orig_text") or "").strip()
        gender = it.get("gender", "ប្រុស")
        echo = it.get("echo", "No")

        if req.include_gender_tag:
            tag_parts = [f"មនុស្ស{gender}"]
            if echo == "Yes":
                tag_parts.append("សំឡេង Echo")
            tag_str = " | ".join(tag_parts)
            content = f"[{tag_str}] {khmer_txt}"
        else:
            content = khmer_txt

        sub_objects.append(srt.Subtitle(index=sid, start=start_td, end=end_td, content=content))

    srt_content = srt.compose(sub_objects)

    # 2. Compile Master Audio using helper matching original filename
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, lambda: compile_master_audio_file(items, out_filename=req.filename, bitrate=req.bitrate or "128k"))
    master_url = res["master_url"] if res else None

    return {
        "success": True,
        "srt_content": srt_content,
        "master_url": master_url
    }

@app.get("/audio_output/{filename}")
def serve_audio(filename: str):
    filepath = os.path.join(AUDIO_OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File Not Found")
    return FileResponse(filepath, media_type="audio/mpeg")

@app.get("/api/health")
def api_health():
    """Health check endpoint to keep cloud servers (e.g. Render) awake and check status."""
    return {
        "status": "ok",
        "service": "PL Khmer Voice Web",
        "cloud": IS_CLOUD,
        "is_pipeline_running": is_pipeline_running,
        "timestamp": int(time.time())
    }

@app.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
