import os
import io
import re
import urllib.parse
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import yt_dlp
import requests

app = FastAPI(title="PECH Tool Extractor & Downloader Backend API")

# Enable CORS for Blogspot and all web origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load YouTube Cookies if configured in Render Environment ──
def get_yt_opts(extra_format=None):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }
    if extra_format:
        opts['format'] = extra_format

    # Check for cookies in Environment Variable or local file
    cookie_env = os.environ.get("YOUTUBE_COOKIE", "").strip()
    if cookie_env:
        cookie_path = os.path.join(os.getcwd(), "cookies.txt")
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(cookie_env)
        opts['cookiefile'] = cookie_path
    elif os.path.exists("cookies.txt"):
        opts['cookiefile'] = "cookies.txt"
    else:
        # Fallback when no cookies: use mobile player clients
        opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'mweb', 'ios'],
                'player_skip': ['webpage', 'configs'],
            }
        }
        
    return opts


@app.get("/")
def home():
    has_cookie = bool(os.environ.get("YOUTUBE_COOKIE") or os.path.exists("cookies.txt"))
    return {
        "status": "Online",
        "service": "PECH Tool Extractor & Downloader API",
        "has_youtube_cookie": has_cookie,
        "version": "1.0.0"
    }


@app.get("/api/info")
@app.get("/info")
def get_media_info(url: str = Query(..., description="Media URL")):
    """Extract media title, duration, thumbnail, and stream formats using yt-dlp."""
    try:
        ydl_opts = get_yt_opts()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Find best MP4 stream with audio
            direct_video_url = None
            if 'formats' in info:
                for f in reversed(info['formats']):
                    if f.get('ext') == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        direct_video_url = f.get('url')
                        break
                if not direct_video_url and info['formats']:
                    direct_video_url = info['formats'][-1].get('url')
            elif 'url' in info:
                direct_video_url = info['url']

            return {
                "success": True,
                "title": info.get("title", "downloaded_media"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
                "direct_url": direct_video_url,
                "platform": info.get("extractor_key", "Media")
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/download")
@app.get("/download")
def download_stream(url: str = Query(..., description="Media URL to download as MP4")):
    """Directly stream and download the MP4 media file to the user's browser."""
    try:
        ydl_opts = get_yt_opts(extra_format='best[ext=mp4]/best')
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "media")
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:60]
            
            # Extract direct URL
            stream_url = info.get("url")
            if not stream_url and 'formats' in info:
                for f in reversed(info['formats']):
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        stream_url = f.get('url')
                        break
                if not stream_url:
                    stream_url = info['formats'][-1].get('url')

            if not stream_url:
                raise HTTPException(status_code=404, detail="Stream URL not found")

            # Stream the media content directly to the client browser
            req = requests.get(stream_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
            
            def iterfile():
                for chunk in req.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        yield chunk

            encoded_filename = urllib.parse.quote(f"{safe_title}.mp4")
            headers = {
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": req.headers.get("Content-Type", "video/mp4")
            }
            return StreamingResponse(iterfile(), headers=headers)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
