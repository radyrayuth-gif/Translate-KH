import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment, effects

st.set_page_config(page_title="Khmer TTS - Auto Speed Sync", page_icon="🎙️")

async def fetch_audio(text, voice, rate_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except: return None

async def generate_forced_speed_audio(srt_content, voice, base_speed):
    try:
        subs = list(srt.parse(srt_content))
    except: return None

    rate_str = f"{base_speed:+d}%"
    total_ms = int(subs[-1].end.total_seconds() * 1000) + 1000
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)
    
    for i, sub in enumerate(subs):
        audio_data = await fetch_audio(sub.content, voice, rate_str)
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            segment = effects.strip_silence(segment, silence_thresh=-50, padding=0)

            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            
            # រកមើលម៉ោងចាប់ផ្ដើមនៃលេខរៀងបន្ទាប់ (បើមាន)
            next_start_ms = int(subs[i+1].start.total_seconds() * 1000) if i + 1 < len(subs) else end_ms
            
            # រយៈពេលអតិបរមាដែលអនុញ្ញាតឱ្យនិយាយ (កុំឱ្យជាន់លេខរៀងបន្ទាប់)
            allowed_duration = next_start_ms - start_ms
            current_duration = len(segment)

            # --- Logic បង្ខំពន្លឿន ---
            if current_duration > allowed_duration and allowed_duration > 0:
                # គណនាល្បឿនដែលត្រូវបង្កើន ដើម្បីឱ្យចប់មុនលេខរៀងបន្ទាប់
                force_speed_ratio = current_duration / allowed_duration
                
                # ពន្លឿនដោយប្រើ chunk_size ខ្លី ដើម្បីឱ្យរលូនមិនស្គប់
                segment = effects.speedup(
                    segment, 
                    playback_speed=min(force_speed_ratio, 2.5), # បង្កើនល្បឿនបានរហូតដល់ ២.៥ដង
                    chunk_size=40, 
                    crossfade=15
                )
                
                # បើនៅតែលើសបន្តិច (ដោយសារក្បួន speedup) យើងកាត់តម្រឹមឱ្យស្មើ allowed_duration តែម្តង
                segment = segment[:allowed_duration]

            # Overlay ចូលក្នុង Timeline ឱ្យចំម៉ោងដែលកំណត់
            final_audio = final_audio.overlay(segment, position=start_ms)

    # បង្កើនកម្រិតសំឡេងឱ្យស្មើគ្នា
    final_audio = effects.normalize(final_audio)
    
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="192k")
    return buffer.getvalue()

# --- UI ---
st.title("🎙️ Khmer TTS - បង្ខំពន្លឿនស្វ័យប្រវត្តិ")
st.info("បច្ចេកទេស៖ ប្រសិនបើសំឡេងទី១ អានមិនទាន់ចប់ វានឹងពន្លឿនឱ្យលឿនបំផុតដើម្បីបញ្ចប់មុនលេខរៀងទី២ ចាប់ផ្ដើម។")

voice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
speed = st.slider("ល្បឿនអានទូទៅ (%):", -50, 50, 15)
srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT:", height=250)

if st.button("🔊 ផលិតសំឡេង Sync"):
    if srt_text.strip():
        with st.spinner("កំពុងគណនា និងបង្ខំល្បឿនឱ្យត្រូវម៉ោង..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio = loop.run_until_complete(generate_forced_speed_audio(srt_text, voice, speed))
            if audio:
                st.audio(audio)
                st.download_button("📥 ទាញយក MP3", audio, "forced_sync.mp3")
