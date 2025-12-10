import whisper
import google.generativeai as genai
import os

# Global variable to store the loaded model
model = None

def load_whisper_model(model_size="tiny"):
    global model
    if model is None:
        print(f"Loading Whisper model: {model_size}...")
        model = whisper.load_model(model_size)
        print("Whisper model loaded.")
    return model

def transcribe_audio(audio_path):
    model = load_whisper_model()
    print(f"Transcribing {audio_path}...")
    result = model.transcribe(audio_path)
    return result

def format_segments(segments):
    formatted_text = ""
    for segment in segments:
        start = segment["start"]
        end = segment["end"]
        text = segment["text"]
        speaker = segment.get("speaker", "")
        speaker_str = f"[{speaker}] " if speaker else ""
        formatted_text += f"[{start:.2f}s -> {end:.2f}s] {speaker_str}{text}\n"
    return formatted_text

def summarize_text(transcription_text, api_key):
    if not api_key:
        return "Error: No Google API Key provided."
    
    try:
        genai.configure(api_key=api_key)
        model_llm = genai.GenerativeModel('models/gemini-2.5-flash')
        
        prompt = (
            f"請根據以下音頻逐字稿，提取主要關鍵點或重要段落，並為每個關鍵點提供大致的起始時間和結束時間。"
            f"時間格式為 `[起始時間s -> 結束時間s]`，摘要內容。\n\n"
            f"逐字稿內容：\n{transcription_text}\n\n"
            f"請以以下格式輸出：\n"
            f"[起始時間s -> 結束時間s] 摘要內容\n"
            f"[起始時間s -> 結束時間s] 摘要內容\n..."
        )
        
        response = model_llm.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def correct_transcription(transcription_text, api_key):
    if not api_key:
        return "Error: No Google API Key provided."
    
    try:
        genai.configure(api_key=api_key)
        model_llm = genai.GenerativeModel('models/gemini-2.5-flash')
        
        prompt = (
            f"請檢查以下音頻逐字稿，並修正其中的錯別字。特別是，請將所有簡體中文字轉換為繁體中文字。"
            f"**重要：請務必保留每一行的時間戳記 `[start -> end]` 和說話者標籤 `[SPEAKER_xx]`，不要修改它們，只需修改文字部分。**"
            f"輸出時，只返回修正後的文本，不需要任何額外的說明或格式。\n\n"
            f"逐字稿內容：\n{transcription_text}\n"
        )
        
        response = model_llm.generate_content(prompt)
        print(f"DEBUG: LLM Correction Response: {response.text[:200]}...") # Log first 200 chars
        return response.text
    except Exception as e:
        print(f"DEBUG: Error in correct_transcription: {str(e)}")
        return f"Error correcting transcription: {str(e)}"

def parse_corrected_segments(corrected_text):
    """
    Parses the corrected text back into a list of segments.
    Assumes the corrected text maintains the line-by-line format:
    [start -> end] text
    """
    segments = []
    
    # Remove markdown code blocks if present
    corrected_text = corrected_text.replace("```python", "").replace("```", "").strip()
    
    lines = corrected_text.strip().split('\n')
    import re
    
    # Regex to extract start, end, speaker (optional), and text
    # Matches: [0.00s -> 5.00s] [SPEAKER_00] Some text
    # Or: [0.00s -> 5.00s] Some text
    # Regex to extract start, end, speaker (optional), and text
    # Matches: [0.00s -> 5.00s] [SPEAKER_00] Some text
    # Or: [0.00s -> 5.00s] Some text
    # Flexible with spaces and 's' unit
    pattern = re.compile(r'\[\s*(\d+\.?\d*)\s*s?\s*->\s*(\d+\.?\d*)\s*s?\s*\]\s*(?:\[(.*?)\])?\s*(.*)')
    
    print(f"DEBUG: Parsing {len(lines)} lines of corrected text.")
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        match = pattern.match(line)
        if match:
            start = float(match.group(1))
            end = float(match.group(2))
            speaker = match.group(3) if match.group(3) else ""
            text = match.group(4).strip()
            
            segment = {
                "start": start,
                "end": end,
                "text": text
            }
            if speaker:
                segment["speaker"] = speaker
                
            segments.append(segment)
        else:
            print(f"DEBUG: Failed to match line: {line}")
            
    print(f"DEBUG: Parsed {len(segments)} segments.")
    return segments

def diarize_audio(audio_path, hf_token, num_speakers=None):
    try:
        from pyannote.audio import Pipeline
        import torch
        
        print(f"Diarizing {audio_path} with num_speakers={num_speakers}...")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        
        if pipeline is None:
            print("Error: Could not load diarization pipeline. Check HF token.")
            return []

        # Use GPU if available
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
            
        if num_speakers:
            diarization = pipeline(audio_path, num_speakers=num_speakers)
        else:
            diarization = pipeline(audio_path)
        
        # Convert to list of dicts
        diarization_result = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            diarization_result.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
            
        with open("debug_diarization.txt", "a", encoding="utf-8") as f:
            f.write(f"Audio: {audio_path}\n")
            f.write(f"Segments found: {len(diarization_result)}\n")
            if len(diarization_result) > 0:
                f.write(f"First segment: {diarization_result[0]}\n")
            else:
                f.write("No segments found.\n")

        print(f"DEBUG: Diarization found {len(diarization_result)} segments.")
        if len(diarization_result) > 0:
            print(f"DEBUG: First segment: {diarization_result[0]}")
            
        return diarization_result
    except Exception as e:
        error_msg = f"Error in diarization: {str(e)}"
        print(error_msg)
        with open("debug_diarization.txt", "a", encoding="utf-8") as f:
            f.write(f"Audio: {audio_path}\n")
            f.write(f"ERROR: {error_msg}\n")
        import traceback
        traceback.print_exc()
        return []

def merge_diarization_with_transcript(transcript_segments, diarization_segments):
    print(f"DEBUG: Merging {len(transcript_segments)} transcript segments with {len(diarization_segments)} diarization segments.")
    
    # Simple merging strategy: assign speaker with max overlap
    for segment in transcript_segments:
        seg_start = segment["start"]
        seg_end = segment["end"]
        
        # Find overlapping diarization segments
        overlaps = {}
        for dia in diarization_segments:
            dia_start = dia["start"]
            dia_end = dia["end"]
            speaker = dia["speaker"]
            
            # Calculate overlap
            overlap_start = max(seg_start, dia_start)
            overlap_end = min(seg_end, dia_end)
            overlap_duration = max(0, overlap_end - overlap_start)
            
            if overlap_duration > 0:
                overlaps[speaker] = overlaps.get(speaker, 0) + overlap_duration
        
        # Assign speaker with max overlap
        if overlaps:
            best_speaker = max(overlaps, key=overlaps.get)
            segment["speaker"] = best_speaker
        else:
            segment["speaker"] = "Unknown"
            
    return transcript_segments
