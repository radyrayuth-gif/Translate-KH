import streamlit as st
import asyncio
import edge_tts
import srt
import io
from pydub import AudioSegment, effects

# កំណត់ការបង្ហាញទំព័រ
st.set_page_config(page_title="Khmer TTS Studio - 320k HQ", page_icon="🎙️")

# --- មុខងារទាញយកសំឡេងពី Microsoft Edge TTS ---
async def fetch_audio(text, voice, rate_str, pitch_str):
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except Exception as e:
        return None

# --- មុខងារកែច្នៃសំឡេងឱ្យពីរោះ និងច្បាស់ ---
async def generate_studio_audio(srt_content, voice, multiplier, pitch_hz):
    try:
        subs = list(srt.parse(srt_content))
    except:
        return None

    # បំប្លែង Speed និង Pitch ទៅជា Format ដែល AI យល់
    percentage = int((multiplier - 1) * 100)
    rate_str = f"{percentage:+d}%"
    pitch_str = f"{pitch_hz:+d}Hz"
    
    # បង្កើតផ្ទៃសំឡេងមេ (ទទេ)
    total_ms = int(subs[-1].end.total_seconds() * 1000) + 1000
    final_audio = AudioSegment.silent(duration=total_ms, frame_rate=44100)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, sub in enumerate(subs):
        status_text.text(f"កំពុងផលិតលេខរៀងទី: {i+1}/{len(subs)}")
        audio_data = await fetch_audio(sub.content, voice, rate_str, pitch_str)
        
        if audio_data:
            segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
            
            # ១. កាត់ផ្នែកស្ងាត់ចេញ (Strip Silence)
            segment = effects.strip_silence(segment, silence_thresh=-50, padding=10)

            # ២. បញ្ចូល Compressor ដើម្បីឱ្យសំឡេងណែន និងច្បាស់ដូចក្នុង Studio
            segment = effects.compress_dynamic_range(segment)

            start_ms = int(sub.start.total_seconds() * 1000)
            
            if i + 1 < len(subs):
                next_start_ms = int(subs[i+1].start.total_seconds() * 1000)
                allowed_duration = next_start_ms - start_ms
                current_duration = len(segment)

                # ៣. ពន្លឿនបន្ថែមក្នុងករណីសំឡេងវែងជាងម៉ោងកំណត់ (No Gap)
                if current_duration > allowed_duration and allowed_duration > 0:
                    ratio = current_duration / allowed_duration
                    segment = effects.speedup(segment, playback_speed=min(ratio, 2.0), chunk_size=50, crossfade=15)
                    segment = segment[:allowed_duration]

            # បញ្ចូលក្នុង Master Audio
            final_audio = final_audio.overlay(segment, position=start_ms)
        
        progress_bar.progress((i + 1) / len(subs))

    # ៤. ជំហានចុងក្រោយ៖ Normalize ឱ្យឮច្បាស់ពេញកម្រិត
    final_audio = effects.normalize(final_audio)
    
    # ៥. នាំចេញជាឯកសារ MP3 ក្នុងកម្រិត 320k (គុណភាពខ្ពស់បំផុត)
    buffer = io.BytesIO()
    final_audio.export(buffer, format="mp3", bitrate="320k")
    status_text.success("ការផលិតបានជោគជ័យ!")
    return buffer.getvalue()

# --- ចំណុចប្រទាក់អ្នកប្រើ (UI) ---
st.title("🎙️ Khmer TTS Studio (320k HQ)")
st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    voice = st.selectbox("ជ្រើសរើសអ្នកអាន:", ["km-KH-SreymomNeural", "km-KH-PisethNeural"])
    speed_multiplier = st.slider("ល្បឿនអាន (Speed):", 0.5, 2.0, 1.2, step=0.1, format="%.1fx")

with col2:
    pitch_val = st.slider("កម្ពស់សំឡេង (Pitch):", -20, 20, 0, step=1, format="%dHz")
    st.write("🔧 **ការកំណត់បច្ចេកទេស:**")
    st.caption("✅ Bitrate: 320k (Studio Quality)")
    st.caption("✅ Audio Effect: Dynamic Compressor")

srt_text = st.text_area("បញ្ចូលអត្ថបទ SRT របស់អ្នក:", height=250, placeholder="1\n00:00:00,500 --> 00:00:02,000\nសួស្ដីបងប្អូនទាំងអស់គ្នា...")

if st.button("🔊 ចាប់ផ្ដើមផលិតសំឡេង 320k", use_container_width=True):
    if srt_text.strip():
        with st.spinner("កំពុង Render សំឡេងកម្រិតខ្ពស់..."):
            audio = asyncio.run(generate_studio_audio(srt_text, voice, speed_multiplier, pitch_val))
            if audio:
                st.audio(audio)
                st.download_button(
                    label="📥 ទាញយក MP3 (320k HQ)",
                    data=audio,
                    file_name="khmer_tts_320k_hq.mp3",
                    mime="audio/mp3"
                )
    else:
        st.warning("សូមបញ្ចូលអត្ថបទ SRT ជាមុនសិន!")

st.divider()
st.caption("Khmer AI Voice Engine - Optimized for Facebook & TikTok Content")
