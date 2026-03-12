import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment, effects

st.set_page_config(page_title="Khmer TTS - Natural Human Voice", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

def process_natural_voice(audio, target_ms):
    """កែសម្រួលឱ្យសំឡេងហាប់ណែន និងតភ្ជាប់គ្នាបានល្អ"""
    # ១. កាត់ចន្លោះស្ងាត់ដែល AI បង្កើតចោល (កាត់សូរសព្ទដកដង្ហើម)
    audio = effects.strip_silence(audio, silence_thresh=-50, padding=10)
    
    current_ms = len(audio)
    if target_ms > 0 and current_ms > target_ms:
        # ២. ពន្លឿនឱ្យត្រូវម៉ោង SRT ដោយរក្សាគុណភាពខ្ពស់
        speed_ratio = current_ms / target_ms
        # ប្រើ speedup ជាមួយ chunk ខ្លី ដើម្បីឱ្យរលូន
        audio = effects.speedup(audio, playback_speed=min(speed_ratio, 1.8), chunk_size=50, crossfade=20)
    
    return audio[:target_ms] if target_ms > 0 else audio

async def generate_human_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    total_ms = int(subs[-1].end.total_seconds() * 1000)
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)
    
    for sub in subs:
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            
            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            target_dur = end_ms - start_ms
            
            # កែសម្រួលសំឡេងឱ្យ "ហាប់" ដូចមនុស្សនិយាយ
            processed_segment = process_natural_voice(segment, target_dur)
            
            # ប្រើ Overlay ជាមួយកម្រិត Gain បន្តិចដើម្បីឱ្យសំឡេងច្បាស់
            final_audio = final_audio.overlay(processed_segment, position=start_ms)

    # បង្កើនកម្រិតសំឡេងឱ្យស្មើគ្នា (Normalization)
    final_audio = effects.normalize(final_audio)
    
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - កំណែអានរលូនដូចមនុស្ស")
st.info("កូដនេះលុបចន្លោះ 'ដកដង្ហើម' ចោល និងធ្វើឱ្យសំឡេងតភ្ជាប់គ្នាបានរលូនបំផុត។")

voice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអានមូលដ្ឋាន (%):", -50, 50, 15)
srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=200)

if st.button("🔊 ផលិតសំឡេងមនុស្ស"):
    if srt_text.strip():
        with st.spinner("កំពុងកែសម្រួលរលកសំឡេង..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio = loop.run_until_complete(generate_human_audio(srt_text, voice, speed))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3 (Human Flow)", audio, "human_khmer.mp3")
