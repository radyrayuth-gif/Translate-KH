import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment

st.set_page_config(page_title="Khmer TTS - Smooth Sound", page_icon="🎙️")

def trim_silence(audio, threshold=-50.0):
    """កាត់ចន្លោះស្ងាត់ចេញ ដើម្បីកុំឱ្យសំឡេងជាន់គ្នា"""
    start_trim = 0
    while start_trim < len(audio) and audio[start_trim:start_trim+10].dBFS < threshold:
        start_trim += 10
    end_trim = 0
    while end_trim < len(audio) and audio[len(audio)-end_trim-10:len(audio)-end_trim].dBFS < threshold:
        end_trim += 10
    return audio[start_trim:len(audio)-end_trim]

async def fetch_audio(text, voice, rate_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_smooth_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    total_ms = int(subs[-1].end.total_seconds() * 1000) + 500
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)

    for sub in subs:
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            segment = trim_silence(segment)
            
            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            target_dur = end_ms - start_ms
            
            # --- ដំណោះស្រាយសំឡេងរលូន ---
            # បើលើសម៉ោង SRT បន្តិចបន្តួច យើងមិនបាច់ Speedup ទេ គឺប្រើវិធីកាត់កន្ទុយ (Fade out) ជំនួស
            # ធ្វើបែបនេះសំឡេងនឹងមិនរដិបរដុប ឬស្រគាត្រចៀកឡើយ
            if len(segment) > target_dur:
                ratio = len(segment) / target_dur
                if ratio > 1.1: # បើលើសខ្លាំង ទើបប្រើ Speedup តិចៗ
                    from pydub.effects import speedup
                    # កែ chunk_size ឱ្យតូច (30ms) ដើម្បីឱ្យសំឡេងហាប់ល្អ
                    segment = speedup(segment, playback_speed=min(ratio, 1.5), chunk_size=30, crossfade=10)
                
                # កាត់តម្រឹមឱ្យចំម៉ោង និងបន្ថែម Fade out បន្តិចដើម្បីកុំឱ្យដាច់សំឡេងឆៅៗ
                segment = segment[:target_dur].fade_out(20)

            final_audio = final_audio.overlay(segment, position=start_ms)

    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="192k") # បង្កើន Bitrate ឱ្យច្បាស់ខ្លាំង
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Smooth Version")
st.info("កូដថ្មីនេះបានបង្កើន Bitrate និងកែសម្រួលល្បឿនឱ្យឮរលូន មិនស្រគាត្រចៀក។")

voice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនមូលដ្ឋាន (%):", -50, 50, 10) # បន្ថយ Slider មកត្រឹម +50 វិញដើម្បីសុវត្ថិភាពសំឡេង
srt_text = st.text_area("បញ្ចូល SRT:", height=200)

if st.button("🔊 ផលិតសំឡេងច្បាស់"):
    if srt_text.strip():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio = loop.run_until_complete(generate_smooth_audio(srt_text, voice, speed))
        if audio:
            st.audio(audio)
            st.download_button("📥 ទាញយក (High Quality)", audio, "smooth_audio.mp3")
