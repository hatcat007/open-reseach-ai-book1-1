import re
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

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
    match = re.search(r"watch\?v=([^&]+)", video_url)
    if match:
        video_id = match.group(1)
    else:
        # Shortened URL: https://youtu.be/VIDEO_ID
        match = re.search(r"youtu\.be/([^&?]+)", video_url)
        if match:
            video_id = match.group(1)

    if not video_id:
        return "Error: Could not extract video ID from the URL. Please provide a valid YouTube video URL (e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ or https://youtu.be/dQw4w9WgXcQ)."

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to find a manually created transcript in English or any other language
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except NoTranscriptFound:
            # If no manual English transcript, try to find any manually created transcript
            manual_transcripts = [t for t in transcript_list if not t.is_generated]
            if manual_transcripts:
                transcript = manual_transcripts[0] # Take the first one found
            else:
                # If no manual transcript at all, try to find an auto-generated English transcript
                try:
                    transcript = transcript_list.find_generated_transcript(['en'])
                except NoTranscriptFound:
                    # If no auto-generated English, take the first available generated transcript
                    generated_transcripts = [t for t in transcript_list if t.is_generated]
                    if generated_transcripts:
                        transcript = generated_transcripts[0]
                    else:
                        # If still no transcript, raise the original error for a specific language if needed,
                        # or handle as no transcript available at all.
                        # For this implementation, we'll fall back to fetching the first available transcript.
                        transcript = transcript_list.fetch_all_transcripts()[0] # Fallback, might need better logic


        full_transcript = "\n".join([item['text'] for item in transcript.fetch()])
        return full_transcript
    except TranscriptsDisabled:
        return f"Error: Transcripts are disabled for video ID: {video_id}"
    except NoTranscriptFound:
        return f"Error: No transcript found for video ID: {video_id}. This might be because the video is live, has no captions, or they are not available in a processable format."
    except Exception as e:
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