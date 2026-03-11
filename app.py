import streamlit as st
import asyncio
import edge_tts
import srt
import io
import re
from pydub import AudioSegment

# --- កំណត់ទំព័រ ---
st.set_page_config(page_title="Khmer TTS - Perfect Sync", page_icon="🎙️")

async def fetch_audio_chunk(text, voice, rate_str, pitch_str):
    try:
        clean_text = re.sub(r'[^\u1780-\u17FF\u19E0-\u19FFa-zA-Z0-9\s\.\?\!]', '', text)
        if not clean_text.strip(): return None
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate_str, pitch=pitch_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_audio(srt_content, voice, rate, pitch):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{rate:+d}%"
    pitch_str = f"{pitch:+d}Hz"

    tasks = [fetch_audio_chunk(sub.content, voice, rate_str, pitch_str) for sub in subs]
    audio_chunks = await asyncio.gather(*tasks)

    # បង្កើត Timeline សំឡេង (ចាប់ផ្ដើមពីស្ងាត់)
    final_combined = AudioSegment.silent(duration=0)
    
    for i, sub in enumerate(subs):
        if audio_chunks[i]:
            segment = AudioSegment.from_file(io.BytesIO(audio_chunks[i]), format="mp3")
            
            # ១. គណនារយៈពេលដែលត្រូវការក្នុង SRT (Duration)
            srt_start_ms = int(sub.start.total_seconds() * 1000)
            srt_end_ms = int(sub.end.total_seconds() * 1000)
            target_duration = srt_end_ms - srt_start_ms
            
            # ២. កែសម្រួលល្បឿនសំឡេង AI ឱ្យត្រូវនឹង target_duration (Time Stretching)
            # បើ AI អានវែងពេក វានឹងពន្លឿនឱ្យល្មមនឹងម៉ោង SRT
            current_segment_duration = len(segment)
            if current_segment_duration > 0:
                speed_ratio = current_segment_duration / target_duration
                # បើខុសគ្នាខ្លាំងពេក (លើសពី 10%) ទើបយើង Adjust
                if speed_ratio > 1.1 or speed_ratio < 0.9:
                    segment = segment._spawn(segment.raw_data, overrides={
                        "frame_rate": int(segment.frame_rate * speed_ratio)
                    }).set_frame_rate(segment.frame_rate)

            # ៣. បញ្ចូលទៅក្នុង Timeline ឱ្យចំម៉ោង Start
            current_len = len(final_combined)
            if srt_start_ms > current_len:
                final_combined += AudioSegment.silent(duration=srt_start_ms - current_len)
            
            # Overlay ដើម្បីកុំឱ្យវាដាច់ ឬគាំង ប្រសិនបើមានការជាន់គ្នាតិចតួច
            final_combined = final_combined.overlay(segment, position=srt_start_ms)
            
            # បន្ថែម Silence បន្តិចដើម្បីធានាថា Duration សរុបកើនឡើងតាម Timeline
            if len(final_combined) < srt_end_ms:
                final_combined += AudioSegment.silent(duration=srt_end_ms - len(final_combined))

    buffer = io.BytesIO()
    final_combined.export(buffer, format="mp3")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - Perfect Sync")
st.warning("ប្រព័ន្ធនឹងពន្លឿន ឬបន្ថយសំឡេងដោយស្វ័យប្រវត្តិ ដើម្បីឱ្យត្រូវនឹងម៉ោងក្នុង SRT របស់បង។")

with st.sidebar:
    voice_choice = st.selectbox("អ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
    speed = st.slider("ល្បឿនមូលដ្ឋាន (%):", -50, 100, 20)
    pitch = st.slider("កម្រិតសំឡេង (Hz):", -20, 20, 0)

srt_input = st.text_area("បញ្ចូល SRT:", height=300)

if st.button("🔊 ផលិតសំឡេង Sync"):
    if srt_input.strip():
        with st.spinner("កំពុងគណនាម៉ោងឱ្យត្រូវនឹងវីដេអូ..."):
            final_audio = asyncio.run(generate_audio(srt_input, voice_choice, speed, pitch))
            if final_audio:
                st.audio(final_audio)
                st.download_button("📥 ទាញយក MP3", final_audio, "sync_khmer_audio.mp3")
