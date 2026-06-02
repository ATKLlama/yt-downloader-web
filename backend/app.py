from flask import Flask, request, send_file, abort
import os
import yt_dlp
import imageio_ffmpeg

# CONFIG
DOWNLOAD_FOLDER = "Downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)

@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url")
    format_type = request.form.get("format")

    if not url or format_type not in ["mp3", "mp4"]:
        return abort(400, "Invalid input")

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    out_path = os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s")

    if format_type == "mp4":
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
            "merge_output_format": "mp4",
            "outtmpl": out_path,
            "ffmpeg_location": ffmpeg_path
        }
    else:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_path,
            "ffmpeg_location": ffmpeg_path,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url)
        filename = ydl.prepare_filename(info)
        if format_type == "mp3":
            filename = os.path.splitext(filename)[0] + ".mp3"

    return send_file(filename, as_attachment=True)

@app.route("/", methods=["GET"])
def home():
    return "YT Downloader Backend is running! POST to /download"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)