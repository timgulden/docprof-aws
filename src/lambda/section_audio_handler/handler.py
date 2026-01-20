"""
Section Audio Handler - TTS audio generation with speech marks for text highlighting.

Endpoints:
- GET /courses/section/{sectionId}/audio - Stream lecture audio (MP3)
- GET /courses/section/{sectionId}/speech-marks - Get word/sentence timing data

Features:
- On-demand audio generation using AWS Polly Neural voices
- Word-level speech marks for text highlighting during playback
- S3 caching for generated audio and marks
- Handles long lectures by chunking with seamless playback
"""

import base64
import json
import logging
import os
import uuid
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from shared.db_utils import get_db_connection
from shared.response import success_response, error_response
from shared.polly_client import (
    synthesize_lecture_with_marks,
    synthesize_speech,
    get_speech_marks,
    chunk_text_for_polly,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# S3 bucket for audio cache
AUDIO_CACHE_BUCKET = os.getenv("AUDIO_CACHE_BUCKET", "docprof-dev-audio-cache")
AUDIO_CACHE_PREFIX = "lectures"

# Initialize S3 client
s3_client = boto3.client("s3")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler - routes to audio or speech-marks endpoint.
    
    Routes:
    - GET /courses/section/{sectionId}/audio
    - GET /courses/section/{sectionId}/speech-marks
    """
    try:
        # Extract path and method
        http_method = event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", ""))
        path = event.get("path", event.get("rawPath", ""))
        
        logger.info(f"Section audio handler: {http_method} {path}")
        
        # Extract section ID from path
        path_params = event.get("pathParameters") or {}
        section_id = path_params.get("sectionId")
        
        if not section_id:
            return error_response("Missing sectionId in path", status_code=400)
        
        # Validate UUID format
        try:
            uuid.UUID(section_id)
        except ValueError:
            return error_response(f"Invalid sectionId format: {section_id}", status_code=400)
        
        # Extract user ID from Cognito
        user_id = extract_user_id(event)
        if not user_id:
            return error_response("Authentication required", status_code=401)
        
        # Route to appropriate handler
        if path.endswith("/audio"):
            return handle_audio_request(section_id, user_id, event)
        elif path.endswith("/speech-marks"):
            return handle_speech_marks_request(section_id, user_id, event)
        else:
            return error_response(f"Unknown endpoint: {path}", status_code=404)
            
    except Exception as e:
        logger.error(f"Error in section audio handler: {e}", exc_info=True)
        return error_response(f"Internal error: {str(e)}", status_code=500)


def handle_audio_request(
    section_id: str,
    user_id: str,
    event: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle GET /courses/section/{sectionId}/audio
    
    Returns:
    - Audio bytes (MP3) with appropriate headers for streaming
    - Generates audio on-demand if not cached
    """
    logger.info(f"Audio request for section {section_id} by user {user_id}")
    
    # Verify user has access to this section
    section_data, course_data = get_section_and_verify_access(section_id, user_id)
    if not section_data:
        return error_response("Section not found", status_code=404)
    if not course_data:
        return error_response("Access denied", status_code=403)
    
    # Get lecture script
    lecture_script = get_lecture_script(section_id, user_id)
    if not lecture_script:
        return error_response(
            "Lecture not found. Generate the lecture first.",
            status_code=404
        )
    
    # Check S3 cache
    cache_key = f"{AUDIO_CACHE_PREFIX}/{section_id}/audio.mp3"
    
    # Generate audio if not cached
    if not s3_object_exists(cache_key):
        logger.info(f"Generating audio for section {section_id} ({len(lecture_script)} chars)")
        
        try:
            audio_bytes, speech_marks = synthesize_lecture_with_marks(lecture_script)
            
            # Cache audio
            save_to_s3_cache(cache_key, audio_bytes, content_type="audio/mpeg")
            
            # Cache speech marks
            marks_key = f"{AUDIO_CACHE_PREFIX}/{section_id}/speech-marks.json"
            save_to_s3_cache(
                marks_key,
                json.dumps(speech_marks).encode('utf-8'),
                content_type="application/json"
            )
            
            logger.info(
                f"Generated and cached audio for section {section_id}: "
                f"{len(audio_bytes)} bytes, {len(speech_marks)} marks"
            )
            
        except Exception as e:
            logger.error(f"Failed to generate audio: {e}", exc_info=True)
            return error_response(f"Failed to generate audio: {str(e)}", status_code=500)
    
    # Generate presigned URL for audio (valid for 1 hour)
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': AUDIO_CACHE_BUCKET,
                'Key': cache_key
            },
            ExpiresIn=3600  # 1 hour
        )
        
        logger.info(f"Returning presigned URL for section {section_id}")
        return success_response({
            "section_id": section_id,
            "audio_url": presigned_url,
            "cached": True
        })
        
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}", exc_info=True)
        return error_response(f"Failed to generate presigned URL: {str(e)}", status_code=500)


def handle_speech_marks_request(
    section_id: str,
    user_id: str,
    event: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle GET /courses/section/{sectionId}/speech-marks
    
    Returns:
    - JSON with word/sentence timing data
    - Generates marks on-demand if not cached
    """
    logger.info(f"Speech marks request for section {section_id} by user {user_id}")
    
    # Verify user has access to this section
    section_data, course_data = get_section_and_verify_access(section_id, user_id)
    if not section_data:
        return error_response("Section not found", status_code=404)
    if not course_data:
        return error_response("Access denied", status_code=403)
    
    # Get lecture script
    lecture_script = get_lecture_script(section_id, user_id)
    if not lecture_script:
        return error_response(
            "Lecture not found. Generate the lecture first.",
            status_code=404
        )
    
    # Check S3 cache
    marks_key = f"{AUDIO_CACHE_PREFIX}/{section_id}/speech-marks.json"
    cached_marks = get_from_s3_cache(marks_key)
    
    if cached_marks:
        logger.info(f"Returning cached speech marks for section {section_id}")
        marks = json.loads(cached_marks.decode('utf-8'))
        return success_response({
            "section_id": section_id,
            "marks": marks,
            "mark_count": len(marks),
            "cached": True,
        })
    
    # Check if audio was generated (marks would be cached together)
    audio_key = f"{AUDIO_CACHE_PREFIX}/{section_id}/audio.mp3"
    if not s3_object_exists(audio_key):
        # Generate audio + marks together
        logger.info(f"Generating audio and marks for section {section_id}")
        
        try:
            audio_bytes, speech_marks = synthesize_lecture_with_marks(lecture_script)
            
            # Cache both
            save_to_s3_cache(audio_key, audio_bytes, content_type="audio/mpeg")
            save_to_s3_cache(
                marks_key,
                json.dumps(speech_marks).encode('utf-8'),
                content_type="application/json"
            )
            
            return success_response({
                "section_id": section_id,
                "marks": speech_marks,
                "mark_count": len(speech_marks),
                "cached": False,
            })
            
        except Exception as e:
            logger.error(f"Failed to generate speech marks: {e}", exc_info=True)
            return error_response(f"Failed to generate speech marks: {str(e)}", status_code=500)
    
    # Audio exists but marks don't - regenerate marks only
    logger.info(f"Regenerating speech marks for section {section_id}")
    
    try:
        # For marks-only generation, we don't need to generate audio again
        # but we do need to process chunks consistently
        chunks = chunk_text_for_polly(lecture_script)
        all_marks = []
        cumulative_time = 0
        cumulative_chars = 0
        
        for i, (chunk_text, byte_offset) in enumerate(chunks):
            marks_result = get_speech_marks(chunk_text)
            
            # Adjust timing for this chunk
            for mark in marks_result.marks:
                all_marks.append({
                    'time': mark.time + cumulative_time,
                    'type': mark.type,
                    'start': mark.start + cumulative_chars,
                    'end': mark.end + cumulative_chars,
                    'value': mark.value,
                    'chunk_index': i,
                })
            
            # Estimate duration (will be refined when audio plays)
            # This is approximate - actual sync uses audio currentTime
            estimated_duration = marks_result.marks[-1].time if marks_result.marks else 0
            cumulative_time += estimated_duration
            cumulative_chars += len(chunk_text)
        
        # Cache marks
        save_to_s3_cache(
            marks_key,
            json.dumps(all_marks).encode('utf-8'),
            content_type="application/json"
        )
        
        return success_response({
            "section_id": section_id,
            "marks": all_marks,
            "mark_count": len(all_marks),
            "cached": False,
        })
        
    except Exception as e:
        logger.error(f"Failed to generate speech marks: {e}", exc_info=True)
        return error_response(f"Failed to generate speech marks: {str(e)}", status_code=500)


def get_section_and_verify_access(
    section_id: str,
    user_id: str
) -> tuple[Optional[Dict], Optional[Dict]]:
    """
    Get section data and verify user has access.
    
    Returns:
        Tuple of (section_data, course_data) or (None, None) if not found/denied
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT cs.section_id, cs.course_id, cs.title, cs.estimated_minutes,
                           c.user_id, c.title as course_title
                    FROM course_sections cs
                    JOIN courses c ON cs.course_id = c.course_id
                    WHERE cs.section_id = %s::uuid
                """, (section_id,))
                
                row = cur.fetchone()
                
                if not row:
                    return None, None
                
                section_id_db, course_id, section_title, est_minutes, course_user_id, course_title = row
                
                # Check access
                if str(course_user_id) != user_id:
                    logger.warning(f"User {user_id} denied access to section {section_id}")
                    return {"section_id": section_id}, None
                
                return {
                    "section_id": str(section_id_db),
                    "course_id": str(course_id),
                    "title": section_title,
                    "estimated_minutes": est_minutes,
                }, {
                    "course_id": str(course_id),
                    "user_id": str(course_user_id),
                    "title": course_title,
                }
                
    except Exception as e:
        logger.error(f"Database error checking section access: {e}")
        return None, None


def get_lecture_script(section_id: str, user_id: str) -> Optional[str]:
    """
    Get the lecture script for a section from section_deliveries table.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT lecture_script
                    FROM section_deliveries
                    WHERE section_id = %s::uuid AND user_id = %s::uuid
                    ORDER BY delivered_at DESC
                    LIMIT 1
                """, (section_id, user_id))
                
                row = cur.fetchone()
                if not row:
                    return None

                lecture_script = row[0]
                # Normalize line endings for consistent speech mark offsets
                lecture_script = lecture_script.replace("\r\n", "\n").replace("\r", "\n")
                return lecture_script
                
    except Exception as e:
        logger.error(f"Database error getting lecture script: {e}")
        return None


def extract_user_id(event: Dict[str, Any]) -> Optional[str]:
    """Extract user_id from Cognito authorizer claims."""
    try:
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        claims = authorizer.get("claims", {})
        return claims.get("sub")
    except Exception as e:
        logger.error(f"Error extracting user_id: {e}")
        return None


# --- S3 Cache Functions ---

def get_from_s3_cache(key: str) -> Optional[bytes]:
    """Get object from S3 cache, returns None if not found."""
    try:
        response = s3_client.get_object(Bucket=AUDIO_CACHE_BUCKET, Key=key)
        return response['Body'].read()
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        logger.error(f"S3 get error: {e}")
        return None


def save_to_s3_cache(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Save object to S3 cache."""
    try:
        s3_client.put_object(
            Bucket=AUDIO_CACHE_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info(f"Cached to S3: {key} ({len(data)} bytes)")
    except ClientError as e:
        logger.error(f"S3 put error: {e}")
        raise


def s3_object_exists(key: str) -> bool:
    """Check if an object exists in S3."""
    try:
        s3_client.head_object(Bucket=AUDIO_CACHE_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def audio_response(audio_bytes: bytes) -> Dict[str, Any]:
    """
    Create response for audio data.
    
    Returns base64-encoded audio with appropriate headers for API Gateway
    binary response.
    """
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "audio/mpeg",
            "Content-Length": str(len(audio_bytes)),
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Cache-Control": "public, max-age=86400",  # Cache for 1 day
        },
        "body": base64.b64encode(audio_bytes).decode('utf-8'),
        "isBase64Encoded": True,
    }


def invalidate_audio_cache(section_id: str):
    """
    Invalidate cached audio and marks for a section.
    
    Call this when a lecture is regenerated.
    """
    keys_to_delete = [
        f"{AUDIO_CACHE_PREFIX}/{section_id}/audio.mp3",
        f"{AUDIO_CACHE_PREFIX}/{section_id}/speech-marks.json",
    ]
    
    for key in keys_to_delete:
        try:
            s3_client.delete_object(Bucket=AUDIO_CACHE_BUCKET, Key=key)
            logger.info(f"Deleted cached: {key}")
        except ClientError as e:
            logger.warning(f"Failed to delete {key}: {e}")
