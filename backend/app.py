from flask import Flask, request, send_file, jsonify, after_this_request
from flask_cors import CORS
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
import imageio_ffmpeg

app = Flask(__name__)
CORS(app)

ALLOWED_HOSTS = {
    "youtube.com",
    "youtu.be",
    "m.youtube.com",
    "music.youtube.com",
}

def is_valid_youtube_url(url):
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ["http", "https"]:
            return False
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host in ALLOWED_HOSTS or any(host.endswith("." + h) for h in ALLOWED_HOSTS)
    except Exception:
        return False

def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', "*", name)
    name = re.sub(r"\s+", "*", name)
    return name[:180]

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "message": "YT Downloader Backend Running"
    })

@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url", "").strip()
    format_type = request.form.get("format", "").lower().strip()

    if not url:
        return jsonify({"error": "Missing URL"}), 400
    if format_type not in ["mp3", "mp4"]:
        return jsonify({"error": "Invalid format"}), 400
    if not is_valid_youtube_url(url):
        return jsonify({"error": "Only YouTube URLs are supported"}), 400

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    temp_dir = tempfile.mkdtemp(prefix="ytdl_")

    # Prepare temporary cookie file from environment variable
    cookies_env = os.environ.get("YOUTUBE_COOKIES")
    temp_cookies_path = None
    if cookies_env:
        temp_cookies = tempfile.NamedTemporaryFile(delete=False)
        temp_cookies.write(cookies_env.encode())
        temp_cookies.flush()
        temp_cookies_path = temp_cookies.name

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(temp_dir)
            if temp_cookies_path:
                os.remove(temp_cookies_path)
        except Exception:
            pass
        return response

    ydl_opts = {
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        "ffmpeg_location": ffmpeg_path,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9"
        }
    }

    # Use temporary cookies file if present
    if temp_cookies_path:
        ydl_opts["cookiefile"] = temp_cookies_path

    if format_type == "mp4":
        ydl_opts.update({
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4"
        })
    else:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320"
            }]
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = Path(ydl.prepare_filename(info))
            if format_type == "mp3":
                filename = filename.with_suffix(".mp3")
            if not filename.exists():
                return jsonify({"error": "Download completed but file not found"}), 500

            title = sanitize_filename(info.get("title", info.get("id", "download")))
            download_name = f"{title}{filename.suffix}"

            return send_file(
                str(filename),
                as_attachment=True,
                download_name=download_name
            )

    except yt_dlp.utils.DownloadError as e:
        print("YT-DLP ERROR:", repr(e))
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        print("SERVER ERROR:", repr(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )