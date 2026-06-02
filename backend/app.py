from flask import Flask, request, send_file, abort
from flask_cors import CORS
import os
import yt_dlp
import imageio_ffmpeg

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = "/tmp"  # IMPORTANT for Render (not local folder)


@app.route("/", methods=["GET"])
def home():
    return "Backend running"


@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url")
    format_type = request.form.get("format")

    if not url or format_type not in ["mp3", "mp4"]:
        return abort(400, "Invalid input")

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
        "ffmpeg_location": ffmpeg_path,
        "noplaylist": True,
    }

    if format_type == "mp4":
        ydl_opts["format"] = "bestvideo+bestaudio/best"
        ydl_opts["merge_output_format"] = "mp4"
    else:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            filename = ydl.prepare_filename(info)

            if format_type == "mp3":
                filename = filename.rsplit(".", 1)[0] + ".mp3"

        return send_file(filename, as_attachment=True)

    except Exception as e:
        print("ERROR:", e)
        return abort(500, str(e))


if __name__ == "__main__":
    app.run()