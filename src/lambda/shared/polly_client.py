"""
AWS Polly client for text-to-speech with speech marks support.

Provides:
- synthesize_speech(): Generate audio from text
- get_speech_marks(): Get word/sentence timing metadata for text highlighting
- chunk_text_for_polly(): Split long text into chunks (Polly limit: 6000 chars)
- merge_speech_marks(): Combine speech marks from multiple chunks

Speech marks enable word-level text highlighting during audio playback,
providing a superior experience to paragraph-by-paragraph highlighting.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Initialize Polly client
polly_region = os.getenv("AWS_REGION", "us-east-1")
polly_config = Config(
    read_timeout=60,  # 1 minute timeout for synthesis
    connect_timeout=10,
    retries={'max_attempts': 3}
)
polly_client = boto3.client(
    "polly",
    region_name=polly_region,
    config=polly_config
)

# Default voice configuration
# Matthew (Neural) - clear, professional male voice ideal for lectures
DEFAULT_VOICE_ID = os.getenv("POLLY_VOICE_ID", "Matthew")
DEFAULT_ENGINE = os.getenv("POLLY_ENGINE", "neural")  # Options: standard, neural, long-form, generative
DEFAULT_SAMPLE_RATE = "24000"  # 24kHz for neural voices

# Polly character limits
# Neural voices: 3000 chars max
# Standard voices: 6000 chars max
MAX_CHARS_PER_REQUEST = 3000  # Using neural voices
SAFE_CHUNK_SIZE = 2800  # Leave margin for safety


@dataclass
class SpeechMark:
    """Represents a single speech mark from Polly."""
    time: int  # Milliseconds from start of audio
    type: str  # 'word', 'sentence', 'ssml', 'viseme'
    start: int  # Byte offset in input text
    end: int  # Byte offset in input text (exclusive)
    value: str  # The word/sentence text


@dataclass
class AudioResult:
    """Result from audio synthesis."""
    audio_bytes: bytes
    content_type: str
    sample_rate: str
    voice_id: str
    engine: str
    character_count: int


@dataclass
class SpeechMarksResult:
    """Result from speech marks generation."""
    marks: List[SpeechMark]
    voice_id: str
    engine: str
    character_count: int


def _strip_html_tags(text: str) -> str:
    """
    Strip HTML tags from text while preserving paragraph breaks.
    
    HTML links and other markup shouldn't be read aloud by TTS.
    Preserves paragraph structure for natural speech flow.
    """
    # Protect paragraph breaks
    PARAGRAPH_MARKER = '|||PARAGRAPH_BREAK|||'
    text = text.replace('\n\n', PARAGRAPH_MARKER)
    
    # Remove HTML tags (including attributes)
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up whitespace (preserve single newlines)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    
    # Restore paragraph breaks
    text = text.replace(PARAGRAPH_MARKER, '\n\n')
    
    return text.strip()


def chunk_text_for_polly(
    text: str,
    max_chars: int = SAFE_CHUNK_SIZE
) -> List[Tuple[str, int]]:
    """
    Split text into chunks that fit within Polly's character limit.
    
    Splits at sentence boundaries to maintain natural speech flow.
    Returns list of (chunk_text, byte_offset) tuples where byte_offset
    is the starting position in the original text.
    
    Args:
        text: Text to split
        max_chars: Maximum characters per chunk (default: 2800)
    
    Returns:
        List of (chunk_text, byte_offset) tuples
    """
    # Don't strip HTML - keep original text for accurate byte offsets
    if len(text) <= max_chars:
        return [(text, 0)]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(text):
        # Get a potential chunk
        end_pos = min(current_pos + max_chars, len(text))
        chunk = text[current_pos:end_pos]
        
        # If we're not at the end, find a good break point
        if end_pos < len(text):
            # Look for sentence boundaries in the last 500 chars
            search_start = max(0, len(chunk) - 500)
            search_area = chunk[search_start:]
            
            # Find the last sentence ending
            best_break = -1
            for pattern in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
                pos = search_area.rfind(pattern)
                if pos >= 0:
                    actual_pos = search_start + pos + len(pattern) - 1
                    if actual_pos > best_break:
                        best_break = actual_pos
            
            # Also check for paragraph breaks
            para_break = search_area.rfind('\n\n')
            if para_break >= 0:
                actual_pos = search_start + para_break + 2
                if actual_pos > best_break:
                    best_break = actual_pos
            
            if best_break > 0:
                # Preserve whitespace to keep speech mark offsets aligned
                chunk = chunk[:best_break + 1]
        
        if chunk:
            chunks.append((chunk, current_pos))
        
        current_pos += len(chunk)
        # Do not skip whitespace; keep offsets aligned with original text
    
    logger.info(f"Split {len(text)} chars into {len(chunks)} chunks")
    return chunks


def synthesize_speech(
    text: str,
    voice_id: Optional[str] = None,
    engine: Optional[str] = None,
    output_format: str = "mp3",
    sample_rate: Optional[str] = None,
) -> AudioResult:
    """
    Synthesize speech from text using AWS Polly.
    
    For texts longer than 6000 chars, use chunk_text_for_polly() first
    and call this function for each chunk.
    
    Args:
        text: Text to synthesize (max 6000 chars)
        voice_id: Polly voice ID (default: Matthew)
        engine: Engine type: standard, neural, long-form, generative
        output_format: Audio format: mp3, ogg_vorbis, pcm
        sample_rate: Sample rate in Hz (default: 24000 for neural)
    
    Returns:
        AudioResult with audio bytes and metadata
    
    Raises:
        ValueError: If text exceeds character limit
        ClientError: If Polly API call fails
    """
    # Strip HTML tags
    clean_text = _strip_html_tags(text)
    
    if len(clean_text) > MAX_CHARS_PER_REQUEST:
        raise ValueError(
            f"Text exceeds Polly limit ({len(clean_text)} > {MAX_CHARS_PER_REQUEST}). "
            "Use chunk_text_for_polly() to split text first."
        )
    
    voice = voice_id or DEFAULT_VOICE_ID
    eng = engine or DEFAULT_ENGINE
    rate = sample_rate or DEFAULT_SAMPLE_RATE
    
    logger.info(f"Synthesizing speech: {len(clean_text)} chars, voice={voice}, engine={eng}")
    
    try:
        response = polly_client.synthesize_speech(
            Text=clean_text,
            OutputFormat=output_format,
            VoiceId=voice,
            Engine=eng,
            SampleRate=rate,
        )
        
        # Read the audio stream
        audio_bytes = response['AudioStream'].read()
        
        logger.info(f"Generated {len(audio_bytes)} bytes of audio")
        
        return AudioResult(
            audio_bytes=audio_bytes,
            content_type=response['ContentType'],
            sample_rate=rate,
            voice_id=voice,
            engine=eng,
            character_count=len(clean_text),
        )
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        logger.error(f"Polly synthesis error: {error_code} - {e}")
        raise


def get_speech_marks(
    text: str,
    voice_id: Optional[str] = None,
    engine: Optional[str] = None,
    speech_mark_types: Optional[List[str]] = None,
) -> SpeechMarksResult:
    """
    Get speech marks (timing metadata) for text.
    
    Speech marks provide millisecond timing for words and sentences,
    enabling text highlighting synchronized with audio playback.
    
    Args:
        text: Text to get marks for (max 6000 chars)
        voice_id: Polly voice ID (must match audio synthesis)
        engine: Engine type (must match audio synthesis)
        speech_mark_types: Types to request: word, sentence, ssml, viseme
                          Default: ['word', 'sentence']
    
    Returns:
        SpeechMarksResult with list of SpeechMark objects
    
    Raises:
        ValueError: If text exceeds character limit
        ClientError: If Polly API call fails
    """
    # Don't strip HTML - we need byte offsets to match the original text
    # Polly will skip HTML tags when generating marks automatically
    if len(text) > MAX_CHARS_PER_REQUEST:
        raise ValueError(
            f"Text exceeds Polly limit ({len(text)} > {MAX_CHARS_PER_REQUEST}). "
            "Use chunk_text_for_polly() to split text first."
        )
    
    voice = voice_id or DEFAULT_VOICE_ID
    eng = engine or DEFAULT_ENGINE
    mark_types = speech_mark_types or ['word', 'sentence']
    
    logger.info(f"Getting speech marks: {len(text)} chars, types={mark_types}")
    
    try:
        response = polly_client.synthesize_speech(
            Text=text,
            OutputFormat='json',  # JSON output for speech marks
            VoiceId=voice,
            Engine=eng,
            SpeechMarkTypes=mark_types,
        )
        
        # Parse the JSON lines response
        marks_data = response['AudioStream'].read().decode('utf-8')
        marks = []
        
        for line in marks_data.strip().split('\n'):
            if line:
                mark_dict = json.loads(line)
                marks.append(SpeechMark(
                    time=mark_dict['time'],
                    type=mark_dict['type'],
                    start=mark_dict['start'],
                    end=mark_dict['end'],
                    value=mark_dict['value'],
                ))
        
        logger.info(f"Got {len(marks)} speech marks")
        
        return SpeechMarksResult(
            marks=marks,
            voice_id=voice,
            engine=eng,
            character_count=len(text),
        )
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        logger.error(f"Polly speech marks error: {error_code} - {e}")
        raise


def merge_speech_marks(
    marks_results: List[SpeechMarksResult],
    audio_durations_ms: List[int],
) -> List[Dict[str, Any]]:
    """
    Merge speech marks from multiple chunks into a single timeline.
    
    Adjusts timing offsets so marks from chunk N start after chunk N-1 ends.
    This enables seamless text highlighting across chunk boundaries.
    
    Args:
        marks_results: List of SpeechMarksResult from each chunk
        audio_durations_ms: Duration in ms of each chunk's audio
                           (must be same length as marks_results)
    
    Returns:
        List of speech mark dicts with adjusted 'time' values
    """
    if len(marks_results) != len(audio_durations_ms):
        raise ValueError(
            f"Mismatch: {len(marks_results)} mark results vs {len(audio_durations_ms)} durations"
        )
    
    merged = []
    cumulative_time = 0
    cumulative_chars = 0
    
    for i, (marks_result, duration_ms) in enumerate(zip(marks_results, audio_durations_ms)):
        chunk_start_time = cumulative_time
        chunk_marks_count = len(marks_result.marks)
        
        for mark in marks_result.marks:
            merged.append({
                'time': mark.time + cumulative_time,
                'type': mark.type,
                'start': mark.start + cumulative_chars,
                'end': mark.end + cumulative_chars,
                'value': mark.value,
                'chunk_index': i,
            })
        
        cumulative_time += duration_ms
        cumulative_chars += marks_result.character_count
        
        logger.info(
            f"Chunk {i}: {chunk_marks_count} marks, "
            f"time offset: {chunk_start_time}ms, "
            f"duration: {duration_ms}ms, "
            f"next offset: {cumulative_time}ms"
        )
    
    logger.info(f"Merged {len(merged)} total speech marks, total duration: {cumulative_time}ms")
    return merged


def synthesize_lecture_with_marks(
    text: str,
    voice_id: Optional[str] = None,
    engine: Optional[str] = None,
) -> Tuple[bytes, List[Dict[str, Any]]]:
    """
    Synthesize full lecture audio with speech marks.
    
    Handles chunking automatically for texts exceeding Polly's limit.
    Returns concatenated audio and merged speech marks.
    
    Args:
        text: Full lecture text (any length)
        voice_id: Polly voice ID
        engine: Engine type
    
    Returns:
        Tuple of (audio_bytes, speech_marks_list)
    """
    # Split into chunks
    chunks = chunk_text_for_polly(text)
    
    all_audio = b""
    all_marks_results = []
    audio_durations = []
    
    for i, (chunk_text, byte_offset) in enumerate(chunks):
        logger.info(f"Processing chunk {i + 1}/{len(chunks)} ({len(chunk_text)} chars)")
        
        # Generate speech marks first to get accurate timing
        marks_result = get_speech_marks(
            text=chunk_text,
            voice_id=voice_id,
            engine=engine,
        )
        all_marks_results.append(marks_result)
        
        # Calculate duration from speech marks (much more accurate than byte estimation)
        # Use the last mark's time + a buffer for the last word's duration
        if marks_result.marks:
            last_mark_time = marks_result.marks[-1].time
            # Add buffer based on average word duration or fixed buffer
            avg_word_duration = last_mark_time / len([m for m in marks_result.marks if m.type == 'word']) if len([m for m in marks_result.marks if m.type == 'word']) > 0 else 200
            chunk_duration_ms = int(last_mark_time + min(avg_word_duration * 2, 500))  # Add 2x avg or 500ms max
        else:
            # Fallback: estimate from text length (roughly 150 words per minute = 400ms per word)
            word_count = len(chunk_text.split())
            chunk_duration_ms = word_count * 400
        
        audio_durations.append(chunk_duration_ms)
        logger.info(f"Chunk {i + 1} duration: {chunk_duration_ms}ms (based on speech marks)")
        
        # Generate audio
        audio_result = synthesize_speech(
            text=chunk_text,
            voice_id=voice_id,
            engine=engine,
        )
        all_audio += audio_result.audio_bytes
    
    # Merge speech marks with timing adjustments
    merged_marks = merge_speech_marks(all_marks_results, audio_durations)
    
    logger.info(
        f"Synthesized lecture: {len(all_audio)} bytes audio, "
        f"{len(merged_marks)} speech marks from {len(chunks)} chunks"
    )
    
    return all_audio, merged_marks


def get_available_voices(engine: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get list of available Polly voices.
    
    Args:
        engine: Filter by engine type (optional)
    
    Returns:
        List of voice dictionaries with Id, Name, Gender, LanguageCode
    """
    try:
        params = {}
        if engine:
            params['Engine'] = engine
        
        response = polly_client.describe_voices(**params)
        
        voices = [
            {
                'id': v['Id'],
                'name': v['Name'],
                'gender': v['Gender'],
                'language_code': v['LanguageCode'],
                'language_name': v['LanguageName'],
                'supported_engines': v.get('SupportedEngines', []),
            }
            for v in response['Voices']
        ]
        
        return voices
        
    except ClientError as e:
        logger.error(f"Error listing voices: {e}")
        raise
