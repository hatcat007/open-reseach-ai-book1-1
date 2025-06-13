import re
from loguru import logger
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import xml.etree.ElementTree as ET # Import for ParseError

def get_youtube_transcript(video_url: str) -> str:
    """
    Retrieves the transcript for a given YouTube video URL.

    Args:
        video_url: The full URL of the YouTube video.

    Returns:
        The formatted transcript as a string, or an error message if retrieval fails.
    """
    video_id = None
    # Standard URL: https://www.youtube.com/watch?v=VIDEO_ID
    # Shortened URL: https://youtu.be/VIDEO_ID
    # Live URL: https://www.youtube.com/live/VIDEO_ID
    patterns = [
        r"watch\?v=([^&]+)",
        r"youtu\.be/([^&?]+)",
        r"/live/([^&?/]+)" # Corrected and simplified live pattern
    ]
    for pattern in patterns:
        match = re.search(pattern, video_url)
        if match:
            video_id = match.group(1)
            break

    if not video_id:
        logger.warning(f"Could not extract video ID from URL: {video_url}")
        return "Error: Could not extract video ID from the URL. Please provide a valid YouTube video URL (e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ, https://youtu.be/dQw4w9WgXcQ, or https://www.youtube.com/live/VIDEO_ID)."

    try:
        logger.info(f"Fetching transcripts for video_id: {video_id}")
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        selected_transcript_to_fetch = None

        # Try to find a manually created transcript in English
        try:
            selected_transcript_to_fetch = transcript_list.find_manually_created_transcript(['en'])
            # logger.debug(f"Found manually created English transcript for {video_id}")
        except NoTranscriptFound:
            # logger.debug(f"No manually created English transcript for {video_id}. Looking for other manual transcripts.")
            # If no manual English transcript, try to find any manually created transcript
            # Iterate directly over transcript_list, which yields Transcript objects
            manual_transcripts = [t for t in transcript_list if not t.is_generated]
            if manual_transcripts:
                selected_transcript_to_fetch = manual_transcripts[0] # Take the first one found
                # logger.debug(f"Found other manual transcript for {video_id}: {selected_transcript_to_fetch.language}")
            else:
                # logger.debug(f"No manual transcripts at all for {video_id}. Looking for generated English transcript.")
                # If no manual transcript at all, try to find an auto-generated English transcript
                try:
                    selected_transcript_to_fetch = transcript_list.find_generated_transcript(['en'])
                    # logger.debug(f"Found auto-generated English transcript for {video_id}")
                except NoTranscriptFound:
                    # logger.debug(f"No auto-generated English transcript for {video_id}. Looking for other generated transcripts.")
                    # If no auto-generated English, take the first available generated transcript
                    # Iterate directly over transcript_list
                    generated_transcripts = [t for t in transcript_list if t.is_generated]
                    if generated_transcripts:
                        selected_transcript_to_fetch = generated_transcripts[0]
                        # logger.debug(f"Found other generated transcript for {video_id}: {selected_transcript_to_fetch.language}")
                    # else:
                        # logger.debug(f"No generated transcripts found for {video_id}.")
        
        if not selected_transcript_to_fetch:
            # Construct a list of available transcript languages and types for debugging
            available_transcripts_info = []
            for t in transcript_list: # Iterate directly
                available_transcripts_info.append(f"lang={t.language}, generated={t.is_generated}")
            logger.warning(f"No suitable transcript found for video ID: {video_id}. Available transcripts: [{'; '.join(available_transcripts_info)}]")
            return f"Error: No suitable transcript (manual or generated, preferring English) found for video ID: {video_id}."

        logger.info(f"Fetching transcript for {video_id} using language: {selected_transcript_to_fetch.language}, generated: {selected_transcript_to_fetch.is_generated}")
        try:
            full_transcript = "\\n".join([item['text'] for item in selected_transcript_to_fetch.fetch()])
            return full_transcript
        except ET.ParseError as e:
            logger.warning(f"XML ParseError for preferred transcript (lang={selected_transcript_to_fetch.language}, gen={selected_transcript_to_fetch.is_generated}) for video ID {video_id}. Checking for fallbacks.")
            # Fallback: try any other transcript if the selected one fails to parse
            for fallback_transcript in transcript_list:
                if fallback_transcript != selected_transcript_to_fetch:
                    try:
                        logger.info(f"Attempting fallback transcript (lang={fallback_transcript.language}, gen={fallback_transcript.is_generated}) for video ID {video_id}")
                        full_transcript = "\\n".join([item['text'] for item in fallback_transcript.fetch()])
                        return full_transcript
                    except Exception as fallback_e:
                        logger.warning(f"Fallback transcript failed for video ID {video_id}. Error: {fallback_e}")
                        continue # Try next available transcript
            
            # If all fallbacks fail, then return the original parse error message
            logger.error(f"All fallback transcripts also failed for video ID {video_id}.")
            return f"Error: Failed to parse transcript data from YouTube for video ID {video_id}. The data received was empty or malformed. This can happen with auto-generated captions."

    except TranscriptsDisabled:
        logger.warning(f"Transcripts are disabled for video ID: {video_id}")
        return f"Error: Transcripts are disabled for video ID: {video_id}"
    except NoTranscriptFound:
        logger.warning(f"No transcript found for video ID: {video_id}")
        return f"Error: No transcript found for video ID: {video_id}. This might be because the video is live, has no captions, or they are not available in a processable format."
    except Exception as e:
        logger.exception(f"An unexpected error occurred while fetching transcript for video ID {video_id}")
        return f"Error: An unexpected error occurred while fetching transcript for video ID {video_id}: {str(e)}"

if __name__ == '__main__':
    # Example Usage:
    test_url_standard = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Rick Astley - Never Gonna Give You Up
    test_url_short = "https://youtu.be/dQw4w9WgXcQ"
    test_url_with_timestamp = "https://www.youtube.com/watch?v=FT3YLEc3j9k&t=75s" # Example with timestamp
    test_url_no_transcript = "https://www.youtube.com/watch?v=xxxxxxxxxxx" # A non-existent video or one without transcripts
    test_url_transcripts_disabled = "https://www.youtube.com/watch?v=y2khrwLENGY" # Known to have transcripts disabled for some

    print(f"Transcript for {test_url_standard}:\n{get_youtube_transcript(test_url_standard)}\n")
    # print(f"Transcript for {test_url_short}:\n{get_youtube_transcript(test_url_short)}\n")
    # print(f"Transcript for {test_url_with_timestamp}:\n{get_youtube_transcript(test_url_with_timestamp)}\n")
    # print(f"Transcript for {test_url_no_transcript}:\n{get_youtube_transcript(test_url_no_transcript)}\n")
    # print(f"Transcript for {test_url_transcripts_disabled}:\n{get_youtube_transcript(test_url_transcripts_disabled)}") 