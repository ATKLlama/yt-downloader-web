import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, request, send_file, jsonify, after_this_request
from flask_cors import CORS
import yt_dlp
import imageio_ffmpeg

app = Flask(__name__)
CORS(app)

ALLOWED_HOSTS = {
    "youtube.com",
    "youtu.be",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
}


def is_valid_youtube_url(value: str) -> bool:
    if not isinstance(value, str):
        return False

    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname in ALLOWED_HOSTS or any(hostname.endswith(f".{host}") for host in ALLOWED_HOSTS)


def sanitize_filename(value: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)
    sanitized = re.sub(r"\s+", "_", sanitized).strip("_.")
    return sanitized[:200] or "download"


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "message": "YT Downloader Backend Running"
    })


@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url", "").strip()
    format_type = request.form.get("format", "").strip().lower()

    if not url:
        return jsonify({"error": "Missing URL"}), 400

    if format_type not in {"mp3", "mp4"}:
        return jsonify({"error": "Invalid format"}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Only YouTube URLs are allowed."}), 400

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    temp_dir = tempfile.mkdtemp(prefix="ytdlp_")

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
        return response

    ydl_opts = {
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        "ffmpeg_location": ffmpeg_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    if os.path.exists("cookies.txt"):
        ydl_opts["cookiefile"] = "cookies.txt"

    if format_type == "mp4":
        ydl_opts.update({
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        })
    else:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded = Path(ydl.prepare_filename(info))

            if format_type == "mp3":
                downloaded = downloaded.with_suffix(".mp3")

            if not downloaded.exists():
                return jsonify({"error": "Downloaded file could not be found."}), 500

            title = sanitize_filename(info.get("title", info.get("id", "download")))
            download_name = f"{title}{downloaded.suffix}"

            try:
                return send_file(
                    str(downloaded),
                    as_attachment=True,
                    download_name=download_name,
                )
            except TypeError:
                return send_file(
                    str(downloaded),
                    as_attachment=True,
                    attachment_filename=download_name,
                )

    except yt_dlp.utils.DownloadError:
        return jsonify({"error": "Unable to download the requested media."}), 502
    except Exception:
        return jsonify({"error": "Server error occurred."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
