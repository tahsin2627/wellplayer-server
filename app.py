import os
import subprocess
import xmlrpc.client
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# --- Configuration ---
# The directory where torrents will be downloaded inside the server.
DOWNLOAD_DIR = "/var/data/downloads"
# A secret token to make sure only you can add torrents.
# You will set this in your Render Environment Variables.
RPC_SECRET = os.environ.get("ARIA2_RPC_SECRET", "your-secret-token")
# The URL of your Render service.
# You will set this in your Render Environment Variables.
# e.g., https://wellplayer-backend.onrender.com
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

# --- Initialize Flask App ---
app = Flask(__name__)
CORS(app) # Allow your frontend to talk to this backend

# --- Start Aria2 as a background process when the server starts ---
def start_aria2():
    """Starts the aria2c daemon in the background."""
    try:
        # Ensure the download directory exists
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        
        command = [
            "aria2c",
            "--enable-rpc",
            "--rpc-listen-all=true",
            "--rpc-allow-origin-all",
            f"--rpc-secret={RPC_SECRET}",
            f"--dir={DOWNLOAD_DIR}",
            "--seed-time=0", # Stop seeding immediately after download
            "--daemon=true",
            "--log-level=info",
            "--log=-" # Log to stdout
        ]
        print("Starting aria2c daemon with command...")
        subprocess.run(command, check=True)
        print("Aria2c daemon started successfully.")
        time.sleep(2) # Give it a moment to initialize
    except Exception as e:
        print(f"FATAL: Error starting aria2c: {e}")

# --- Initialize Aria2 RPC Client ---
# This is how we send commands to the running aria2c daemon
# The URL must be internal to the server (localhost)
aria2_rpc_url = f"http://token:{RPC_SECRET}@127.0.0.1:6800/rpc"
server = xmlrpc.client.ServerProxy(aria2_rpc_url)

# --- API Routes ---

@app.route('/')
def index():
    """A simple health check route."""
    return "WellPlayer Aria2 Backend is running!"

@app.route('/add-torrent', methods=['POST'])
def add_torrent():
    """Receives a magnet link from the frontend and adds it to aria2."""
    data = request.get_json()
    magnet_link = data.get('magnet')
    
    if not magnet_link:
        return jsonify({"error": "Magnet link is required"}), 400
    
    try:
        print(f"Adding magnet link: {magnet_link[:50]}...")
        gid = server.aria2.addUri([magnet_link])
        print(f"Successfully added torrent with GID: {gid}")
        return jsonify({"success": True, "gid": gid})
    except Exception as e:
        print(f"Error adding torrent: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/status/<string:gid>', methods=['GET'])
def get_status(gid):
    """Checks the status of a download and returns file info when complete."""
    try:
        status = server.aria2.tellStatus(gid)
        
        if status['status'] == 'complete':
            video_file = None
            largest_size = 0
            for file_info in status['files']:
                if file_info['path'].lower().endswith(('.mp4', '.mkv', '.webm', '.avi')):
                    if int(file_info['length']) > largest_size:
                        largest_size = int(file_info['length'])
                        filename = os.path.basename(file_info['path'])
                        video_file = {
                            "name": filename,
                            "size": largest_size,
                            "stream_url": f"{RENDER_EXTERNAL_URL}/stream/{filename}"
                        }
            
            if video_file:
                 return jsonify({"status": "complete", "file": video_file})
            else:
                 return jsonify({"status": "complete", "error": "No video file found in torrent."})

        elif status['status'] == 'error':
             return jsonify({"status": "error", "message": status.get('errorMessage', 'Unknown error')})
        else:
            return jsonify({
                "status": status['status'],
                "progress": f"{(int(status['completedLength']) / int(status['totalLength'])) * 100:.2f}%" if int(status['totalLength']) > 0 else "0.00%",
                "speed": f"{int(status['downloadSpeed']) / 1024:.2f} KB/s",
                "peers": status.get('numSeeders', '0')
            })
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stream/<path:filename>')
def stream_file(filename):
    """Serves the downloaded video file for streaming."""
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=False)

# --- Start the server ---
if __name__ == '__main__':
    start_aria2()
    port = int(os.environ.get("PORT", 10000))
    # Use Gunicorn in production, but Flask's built-in server for local dev
    # The Dockerfile will use Gunicorn
    app.run(host='0.0.0.0', port=port)
