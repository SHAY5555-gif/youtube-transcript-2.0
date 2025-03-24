import os
import re
import uuid
import logging
import urllib.parse
from flask import Flask, render_template, request, jsonify, send_file, session
import yt_dlp
import threading
import time

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "youtube-audio-downloader-secret")

# Create a directory for temporary files
TEMP_DIR = "temp_downloads"
os.makedirs(TEMP_DIR, exist_ok=True)

# Dictionary to store download progress
download_progress = {}
download_results = {}
download_titles = {}

def is_valid_youtube_url(url):
    """Check if the URL is a valid YouTube URL"""
    if not url:
        return False
    
    parsed_url = urllib.parse.urlparse(url)
    if 'youtube.com' in parsed_url.netloc or 'youtu.be' in parsed_url.netloc:
        return True
    return False

def clean_filename(filename):
    """Clean a filename to make it safe for saving"""
    # Remove invalid characters
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    # Limit length
    return filename[:100]

def download_progress_hook(d):
    """Callback function to track download progress"""
    download_id = d.get('info_dict', {}).get('download_id')
    if not download_id:
        return
    
    if d['status'] == 'downloading':
        # Calculate progress
        if 'total_bytes' in d and d['total_bytes'] > 0:
            progress = float(d['downloaded_bytes']) / float(d['total_bytes']) * 100
        elif 'total_bytes_estimate' in d and d['total_bytes_estimate'] > 0:
            progress = float(d['downloaded_bytes']) / float(d['total_bytes_estimate']) * 100
        else:
            progress = 0
            
        download_progress[download_id] = progress
    elif d['status'] == 'finished':
        download_progress[download_id] = 100

def download_audio(youtube_url, download_id):
    """Download audio from YouTube video"""
    try:
        # Set options for yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': f'{TEMP_DIR}/{download_id}/%(title)s.%(ext)s',
            'progress_hooks': [download_progress_hook],
            'quiet': True,
        }
        
        # Add download_id to info_dict for tracking progress
        class MyLogger(object):
            def debug(self, msg):
                pass
            
            def warning(self, msg):
                pass
            
            def error(self, msg):
                logger.error(msg)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Before download, add custom field to info_dict
            orig_extract_info = ydl.extract_info
            
            def custom_extract_info(url, *args, **kwargs):
                info = orig_extract_info(url, *args, **kwargs)
                if info:
                    info['download_id'] = download_id
                    # Store the title for later use
                    if 'title' in info:
                        download_titles[download_id] = info['title']
                return info
            
            ydl.extract_info = custom_extract_info
            ydl.logger = MyLogger()
            
            # Start the download
            info = ydl.extract_info(youtube_url, download=True)
            
            # Get the output file path
            if 'entries' in info:  # It's a playlist
                info = info['entries'][0]  # Get the first video
            
            title = download_titles.get(download_id, "download")
            mp3_file = f"{TEMP_DIR}/{download_id}/{clean_filename(title)}.mp3"
            
            # Set the result
            download_results[download_id] = {
                'status': 'success',
                'file': mp3_file,
                'title': title
            }
            
    except Exception as e:
        logger.error(f"Error downloading audio: {str(e)}")
        download_results[download_id] = {
            'status': 'error',
            'error': str(e)
        }

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    """Start the download process"""
    youtube_url = request.form.get('youtube_url', '')
    
    if not is_valid_youtube_url(youtube_url):
        return jsonify({
            'status': 'error',
            'message': 'Invalid YouTube URL'
        }), 400
    
    # Generate a unique download ID
    download_id = str(uuid.uuid4())
    
    # Create a directory for this download
    os.makedirs(f"{TEMP_DIR}/{download_id}", exist_ok=True)
    
    # Initialize progress tracking
    download_progress[download_id] = 0
    
    # Start download in background thread
    threading.Thread(
        target=download_audio,
        args=(youtube_url, download_id),
        daemon=True
    ).start()
    
    return jsonify({
        'status': 'started',
        'download_id': download_id
    })

@app.route('/progress/<download_id>')
def progress(download_id):
    """Get the progress of a download"""
    progress = download_progress.get(download_id, 0)
    
    if download_id in download_results:
        result = download_results[download_id]
        return jsonify({
            'status': result['status'],
            'progress': 100,
            'finished': True,
            'title': result.get('title', 'download'),
            'message': result.get('error', '')
        })
    
    return jsonify({
        'status': 'downloading',
        'progress': progress,
        'finished': False
    })

@app.route('/get_file/<download_id>')
def get_file(download_id):
    """Send the downloaded file to the user"""
    if download_id not in download_results:
        return jsonify({
            'status': 'error',
            'message': 'Download not found'
        }), 404
    
    result = download_results[download_id]
    
    if result['status'] != 'success':
        return jsonify({
            'status': 'error',
            'message': result.get('error', 'Unknown error')
        }), 500
    
    # Get the file path
    file_path = result['file']
    title = result.get('title', 'download')
    
    # Send the file
    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"{clean_filename(title)}.mp3",
        mimetype="audio/mpeg"
    )

@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Clean up temporary files after download"""
    download_id = request.form.get('download_id')
    
    if download_id and download_id in download_results:
        try:
            # Remove the temporary directory and its contents
            import shutil
            shutil.rmtree(f"{TEMP_DIR}/{download_id}", ignore_errors=True)
            
            # Clean up tracking dictionaries
            if download_id in download_progress:
                del download_progress[download_id]
            if download_id in download_results:
                del download_results[download_id]
            if download_id in download_titles:
                del download_titles[download_id]
                
            return jsonify({'status': 'success'})
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
    
    return jsonify({'status': 'not_found'}), 404

# Cleanup thread to remove old files periodically
def cleanup_old_files():
    """Remove files older than 1 hour"""
    while True:
        time.sleep(3600)  # Run every hour
        try:
            current_time = time.time()
            for download_folder in os.listdir(TEMP_DIR):
                folder_path = os.path.join(TEMP_DIR, download_folder)
                if os.path.isdir(folder_path):
                    # Check folder creation time
                    creation_time = os.path.getctime(folder_path)
                    if current_time - creation_time > 3600:  # Older than 1 hour
                        import shutil
                        shutil.rmtree(folder_path, ignore_errors=True)
                        logger.debug(f"Cleaned up old folder: {folder_path}")
        except Exception as e:
            logger.error(f"Error during auto cleanup: {str(e)}")

# Start the cleanup thread
threading.Thread(target=cleanup_old_files, daemon=True).start()
