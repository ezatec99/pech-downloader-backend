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


@app.get("/")
def home():
    return {
        "status": "Online",
        "service": "PECH Tool Extractor & Downloader API",
        "version": "1.0.0"
    }


@app.get("/api/info")
def get_media_info(url: str = Query(..., description="Media URL")):
    """Extract media title, duration, thumbnail, and stream formats using yt-dlp."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
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
def download_stream(url: str = Query(..., description="Media URL to download as MP4")):
    """Directly stream and download the MP4 media file to the user's browser."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best[ext=mp4]/best',
        }
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
