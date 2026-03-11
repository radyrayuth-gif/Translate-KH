import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment
from pydub.effects import speedup, strip_silence

# ... (រក្សាទុក function fetch_audio_chunk ដូចដើម)

async def generate_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
        if not subs: return None
    except: return None

    rate_str = f"{base_speed:+d}%"
    tasks = [fetch_audio_chunk(sub.content, voice, rate_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # រក Duration សរុបដើម្បីបង្កើត Background Track តែម្តង
    total_duration_ms = int(subs[-1].end.total_seconds() * 1000) + 500
    final_audio = AudioSegment.silent(duration=total_duration_ms, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # កាត់ចន្លោះស្ងាត់ដែល AI បង្កើតនៅខាងដើម/ចុង (ជួយឱ្យ Sync ខ្លាំង)
            segment = strip_silence(segment, silence_thresh=-50, padding=50)
            
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = srt_end_ms - srt_start_ms
            
            current_dur = len(segment)
            
            # ប្រសិនបើអានយឺតជាង SRT លើសពី 5% ទើបយើងបង្កើនល្បឿន
            if current_dur > target_duration and target_duration > 0:
                ratio = current_dur / target_duration
                if ratio > 1.05: 
                    # កំណត់ ratio ខ្ពស់បំផុតត្រឹម 2.0 ដើម្បីកុំឱ្យសំឡេងបែកខ្លាំង
                    safe_ratio = min(ratio, 2.0)
                    segment = speedup(segment, playback_speed=safe_ratio, chunk_size=50, crossfade=15)
            
            # Overlay ចូលទៅក្នុង Timeline
            final_audio = final_audio.overlay(segment, position=srt_start_ms)

    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="128k")
    return buffer.getvalue()
