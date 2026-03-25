import os
import glob
import re
from flask import Flask, render_template_string, send_from_directory

app = Flask(__name__)

# ==========================================
# ⚙️ SERVER SETTINGS
# ==========================================
USE_HTTPS = False 
PORT = 443 if USE_HTTPS else 80

GIF_DIR = "GIF_Archive"
RAW_DIR = "Raw_Archive"

# ==========================================
# 🌐 HTML TEMPLATES
# ==========================================

# 1. THE GLOBAL GALLERY (Landing Page)
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Booth Global Gallery</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #121212; color: white; text-align: center; margin: 0; padding: 20px; }
        h1 { color: #4CAF50; margin-bottom: 5px; }
        p { color: #aaaaaa; margin-top: 0; margin-bottom: 30px; }
        .gallery { display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; margin-top: 20px; }
        .card { background: #1e1e1e; padding: 15px; border-radius: 10px; width: 100%; max-width: 300px; box-shadow: 0 4px 8px rgba(0,0,0,0.5); transition: transform 0.2s; }
        .card:hover { transform: scale(1.02); }
        .card img { width: 100%; height: 200px; object-fit: cover; border-radius: 5px; display: block; margin-bottom: 15px; border: 1px solid #333; }
        .btn-view { display: block; background: #2196F3; color: white; text-align: center; padding: 12px; border-radius: 5px; font-weight: bold; text-decoration: none; }
        .btn-view:hover { background: #0b7dda; }
    </style>
</head>
<body>
    <h1>🌟 Live Photo Booth Gallery</h1>
    <p>All recent sessions from the event!</p>
    
    <div class="gallery">
        {% for session in sessions %}
            <div class="card">
                {% if session.preview %}
                    <img src="{{ session.preview }}" alt="Session Preview">
                {% else %}
                    <div style="height: 200px; background: #333; border-radius: 5px; margin-bottom: 15px; line-height: 200px; color: #777;">No Preview</div>
                {% endif %}
                <a href="/session/{{ session.id }}" class="btn-view">📂 View Session</a>
            </div>
        {% else %}
            <p>No sessions found yet. Go take some pictures!</p>
        {% endfor %}
    </div>
</body>
</html>
"""

# 2. THE SPECIFIC SESSION PAGE
SESSION_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Photo Booth Session</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #121212; color: white; text-align: center; margin: 0; padding: 20px; }
        h1 { color: #4CAF50; margin-bottom: 5px; }
        p { color: #aaaaaa; margin-top: 0; margin-bottom: 30px; }
        h2 { color: #ffffff; border-bottom: 2px solid #333; padding-bottom: 10px; margin-top: 40px; }
        
        .gallery { display: flex; flex-wrap: wrap; justify-content: center; gap: 15px; margin-top: 20px; }
        .card { background: #1e1e1e; padding: 10px; border-radius: 10px; width: 100%; max-width: 350px; box-shadow: 0 4px 8px rgba(0,0,0,0.5); }
        .card img { width: 100%; border-radius: 5px; display: block; }
        
        .btn-group { display: flex; justify-content: space-between; gap: 10px; margin-top: 10px; }
        .btn { flex: 1; text-align: center; padding: 12px 10px; border-radius: 5px; font-weight: bold; text-decoration: none; display: inline-block; }
        
        .btn-download { background: #2196F3; color: white; }
        .btn-download:hover { background: #0b7dda; }
        .btn-view { background: #4CAF50; color: white; }
        .btn-view:hover { background: #388E3C; }
        
        .nav-back { display: inline-block; margin-bottom: 20px; color: #aaaaaa; text-decoration: none; border: 1px solid #555; padding: 8px 15px; border-radius: 20px; }
        .nav-back:hover { background: #333; color: white; }
        .gif-card { max-width: 500px; margin: 0 auto; border: 2px solid #4CAF50; }
    </style>
</head>
<body>
    <a href="/" class="nav-back">⬅ Back to Gallery</a>
    <h1>📸 Your Photo Booth Memories</h1>
    <p>Save these to your camera roll before you leave!</p>
    
    {% if gif %}
    <h2>🎞️ Your Animated GIF</h2>
    <div class="card gif-card">
        <img src="/files/{{ gif.folder }}/{{ gif.name }}" alt="Animated GIF">
        <div class="btn-group">
            <a href="/files/{{ gif.folder }}/{{ gif.name }}" class="btn btn-view" target="_blank">👁️ Full Size</a>
            <a href="/download/{{ gif.folder }}/{{ gif.name }}" class="btn btn-download" download>📥 Download GIF</a>
        </div>
    </div>
    {% endif %}

    {% if raw_photos %}
    <h2>📷 Your Raw Photos</h2>
    <div class="gallery">
        {% for photo in raw_photos %}
            <div class="card">
                <img src="/files/{{ photo.folder }}/{{ photo.name }}" alt="Raw Photo">
                <div class="btn-group">
                    <a href="/files/{{ photo.folder }}/{{ photo.name }}" class="btn btn-view" target="_blank">👁️ Full Size</a>
                    <a href="/download/{{ photo.folder }}/{{ photo.name }}" class="btn btn-download" download>📥 Download</a>
                </div>
            </div>
        {% endfor %}
    </div>
    {% endif %}
    
    {% if not gif and not raw_photos %}
        <h2>Oops!</h2>
        <p>We couldn't find any photos for this session. They might have been deleted.</p>
    {% endif %}
</body>
</html>
"""

# ==========================================
# 🚦 ROUTES & LOGIC
# ==========================================

def get_all_session_ids():
    """Scans folders and extracts unique session IDs using regex."""
    session_ids = set()
    
    # Check GIFs
    if os.path.exists(GIF_DIR):
        for filepath in glob.glob(f"{GIF_DIR}/booth_*.gif"):
            match = re.search(r'booth_(\d+)\.gif', os.path.basename(filepath))
            if match:
                session_ids.add(match.group(1))
                
    # Check Raw Folders
    if os.path.exists(RAW_DIR):
        for folderpath in glob.glob(f"{RAW_DIR}/Session_*"):
            match = re.search(r'Session_(\d+)', os.path.basename(folderpath))
            if match:
                session_ids.add(match.group(1))
                
    # Return sorted descending (newest first)
    return sorted(list(session_ids), reverse=True)


@app.route("/")
def index():
    """Builds the main landing page showing all sessions."""
    sessions_data = []
    
    for s_id in get_all_session_ids():
        preview_url = None
        
        # Prefer the GIF as the preview thumbnail
        gif_path = os.path.join(GIF_DIR, f"booth_{s_id}.gif")
        if os.path.exists(gif_path):
            preview_url = f"/files/{GIF_DIR}/booth_{s_id}.gif"
        else:
            # Fall back to the first raw photo if no GIF exists
            raw_folder = os.path.join(RAW_DIR, f"Session_{s_id}")
            if os.path.exists(raw_folder):
                raw_files = glob.glob(f"{raw_folder}/*.jpg")
                if raw_files:
                    safe_folder = os.path.dirname(raw_files[0]).replace("\\", "/")
                    name = os.path.basename(raw_files[0])
                    preview_url = f"/files/{safe_folder}/{name}"
                    
        sessions_data.append({
            "id": s_id,
            "preview": preview_url
        })
        
    return render_template_string(INDEX_TEMPLATE, sessions=sessions_data)


@app.route("/session/<session_id>")
def session_page(session_id):
    """Loads the unique gallery for a specific session ID."""
    gif_data = None
    expected_gif = f"booth_{session_id}.gif"
    if os.path.exists(os.path.join(GIF_DIR, expected_gif)):
        gif_data = {"folder": GIF_DIR, "name": expected_gif}
        
    raw_photos_data = []
    expected_raw_folder = f"Session_{session_id}"
    raw_folder_path = os.path.join(RAW_DIR, expected_raw_folder)
    
    if os.path.exists(raw_folder_path):
        for filepath in glob.glob(f"{raw_folder_path}/*.jpg"):
            safe_folder = os.path.dirname(filepath).replace("\\", "/")
            raw_photos_data.append({
                "folder": safe_folder, 
                "name": os.path.basename(filepath)
            })
    raw_photos_data.sort(key=lambda x: x["name"])

    return render_template_string(SESSION_TEMPLATE, gif=gif_data, raw_photos=raw_photos_data)


@app.route("/files/<path:folder>/<name>")
def serve_file(folder, name):
    return send_from_directory(folder, name)


@app.route("/download/<path:folder>/<name>")
def download_file(folder, name):
    return send_from_directory(folder, name, as_attachment=True)


if __name__ == "__main__":
    print(f"Starting Photo Booth Server on port {PORT}...")
    os.makedirs(GIF_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    if USE_HTTPS:
        app.run(host="0.0.0.0", port=PORT, ssl_context="adhoc")
    else:
        app.run(host="0.0.0.0", port=PORT)