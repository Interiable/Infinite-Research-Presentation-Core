from youtube_transcript_api import YouTubeTranscriptApi
from typing import List, Dict

class MediaResearcher:
    """
    Handles extracting information from media sources like YouTube.
    Uses youtube-search-python for search and youtube-transcript-api for subtitles.
    """
    def __init__(self):
        pass

    def search_youtube(self, query: str, max_results: int = 2) -> List[Dict]:
        """Searches YouTube and returns a list of video details."""
        try:
            import urllib.request
            import urllib.parse
            import json
            import re
            
            encoded_search = urllib.parse.quote_plus(query)
            url = f"https://www.youtube.com/results?search_query={encoded_search}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req).read().decode('utf-8')
            
            match = re.search(r'var ytInitialData = ({.*?});</script>', response)
            if not match:
                return []
                
            data = json.loads(match.group(1))
            
            videos = []
            contents = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']
            for item in contents:
                if 'videoRenderer' in item:
                    renderer = item['videoRenderer']
                    videos.append({
                        'title': renderer.get('title', {}).get('runs', [{}])[0].get('text', 'Unknown'),
                        'id': renderer.get('videoId', ''),
                        'url': f"https://www.youtube.com/watch?v={renderer.get('videoId', '')}",
                        'channel': renderer.get('ownerText', {}).get('runs', [{}])[0].get('text', 'Unknown'),
                        'content': ''
                    })
                    if len(videos) >= max_results:
                        break
            return videos
        except Exception as e:
            print(f"⚠️ Native YouTube Search failed: {e}")
            return []

    def get_transcript(self, video_id: str) -> str:
        """Fetches the transcript for a YouTube video using v1.x API."""
        if not video_id:
            return ""
        
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            
            # Version compatibility (1.2.4 uses api.list(), 0.6.x uses list_transcripts)
            api = YouTubeTranscriptApi()
            if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
                transcript_list_obj = YouTubeTranscriptApi.list_transcripts(video_id)
            else:
                transcript_list_obj = api.list(video_id)
            
            transcript_obj = None
            try:
                transcript_obj = transcript_list_obj.find_transcript(['ko', 'en', 'ja', 'es'])
            except Exception:
                # If explicit language is missing, pick the first available
                for t in transcript_list_obj:
                    transcript_obj = t
                    break
            
            if not transcript_obj:
                print(f"⚠️ No transcript object found for video {video_id}.")
                return ""
            
            transcript_data = transcript_obj.fetch()
            
            text_parts = []
            for t in transcript_data:
                if isinstance(t, dict):
                    text_parts.append(t.get('text', ''))
                else:
                    text_parts.append(getattr(t, 'text', ''))
                    
            return " ".join(text_parts).replace('\n', ' ')
            
        except Exception as e:
            # Silence transcript extraction errors for the pipeline, but print a warning for debugging.
            print(f"⚠️ Transcript extraction failed for video {video_id}: {repr(e)}")
            return ""

    def research(self, query: str, max_results: int = 2) -> List[Dict]:
        """High-level function to search and extract transcripts."""
        videos = self.search_youtube(query, max_results=max_results)
        
        valid_videos = []
        for video in videos:
            if video['id']:
                print(f"   🎬 Fetching transcript for: {video['title'][:50]}...")
                transcript = self.get_transcript(video['id'])
                if transcript:
                    video['content'] = transcript
                    video['has_fulltext'] = True
                else:
                    video['content'] = "No transcript available."
                    video['has_fulltext'] = False
                valid_videos.append(video)
        
        return valid_videos
