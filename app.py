import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment, effects

st.set_page_config(page_title="Khmer TTS - Smart Speed", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str, pitch_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_smart_speed_audio(srt_content, voice, multiplier, pitch_hz):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    # កំណត់ល្បឿនមូលដ្ឋាន (Base Speed)
    percentage = int((multiplier - 1) * 100)
    rate_str = f"{percentage:+d}%"
    pitch_str = f"{pitch_hz:+d}Hz"
    
    total_ms = int(subs[-1].end.total_seconds() * 1000) + 1000
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)
    
    progress_bar = st.progress(0)
    
    for i, sub in enumerate(subs):
        audio_data = await fetch_audio(sub.content, voice, rate_str, pitch_str)
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            segment = effects.strip_silence(segment, silence_thresh=-50, padding=10)
            segment = effects.compress_dynamic_range(segment)

            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            
            # រកមើលរយៈពេលដែលអនុញ្ញាតក្នុង SRT (Duration)
            if i + 1 < len(subs):
                next_start_ms = int(subs[i+1].start.total_seconds() * 1000)
                allowed_duration = next_start_ms - start_ms
            else:
                allowed_duration = end_ms - start_ms

            current_duration = len(segment)

            # --- SMART SPEED LOGIC ---
            # ប្រសិនបើសំឡេង AI វែងជាងកាលវិភាគ ទើបយើងពន្លឿន (Speed up the slow parts)
            if current_duration > allowed_duration and allowed_duration > 0:
                ratio = current_duration / allowed_duration
                # ពន្លឿនឱ្យទាន់ពេលវេលា (កម្រិតអតិបរមា 2.0x ដើម្បីកុំឱ្យបែកសំឡេង)
                segment = effects.speedup(segment, playback_speed=min(ratio, 2.0), chunk_size=50, crossfade=15)
                segment = segment[:allowed_duration]
            
            # ប្រសិនបើសំឡេង AI ខ្លីជាងកាលវិភាគ (លឿនស្រាប់) 
            # វានឹងរក្សាល្បឿនដើម ហើយទុកចន្លោះស្ងាត់បន្តិចនៅខាងចុងលេខរៀងនោះ
            
            final_audio = final_audio.overlay(segment, position=start_ms)
        
        progress_bar.progress((i + 1) / len(subs))

    final_audio = effects.normalize(final_audio)
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="320k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Smart Speed (320k)")
st.info("💡 កូដនេះនឹងពន្លឿនតែផ្នែកណាដែលយឺតជាងម៉ោង SRT ប៉ុណ្ណោះ។ ផ្នែកដែលលឿនស្រាប់នឹងរក្សាល្បឿនធម្មតា។")

col1, col2 = st.columns(2)
with col1:
    voice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
    speed_multiplier = st.slider("ល្បឿនមូលដ្ឋាន (Base Speed):", 0.5, 2.0, 1.0, step=0.1, format="%.1fx")
with col2:
    pitch_val = st.slider("កម្ពស់សំឡេង (Pitch):", -20, 20, 0, step=1, format="%dHz")

srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=250)

if st.button("🔊 ផលិតសំឡេង Smart Speed", use_container_width=True):
    if srt_text.strip():
        with st.spinner("កំពុងគណនាល្បឿន និង Render សំឡេង..."):
            audio = asyncio.run(generate_smart_speed_audio(srt_text, voice, speed_multiplier, pitch_val))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3 (320k)", audio, "smart_speed_khmer.mp3")
