import os
import re
import uuid
import logging
import urllib.parse
import requests
import json
import unicodedata
from flask import Flask, render_template, request, jsonify, send_file, session, Response
import yt_dlp
import threading
import time
from datetime import timedelta

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
# Make sure we have a secret key, use default if SESSION_SECRET env var is not available
app.secret_key = os.environ.get("SESSION_SECRET", "youtube-audio-downloader-secret")

# Create a directory for temporary files
TEMP_DIR = "temp_downloads"
os.makedirs(TEMP_DIR, exist_ok=True)

# Dictionary to store download progress
download_progress = {}
download_results = {}
download_titles = {}

# Path to save persistent download results
DOWNLOAD_RESULTS_PATH = os.path.join(TEMP_DIR, 'download_results.json')

# Load stored download results from disk if it exists
def load_download_results():
    global download_results
    try:
        if os.path.exists(DOWNLOAD_RESULTS_PATH):
            with open(DOWNLOAD_RESULTS_PATH, 'r', encoding='utf-8') as f:
                loaded_results = json.load(f)
                # Only restore entries where the file actually exists
                for download_id, result in loaded_results.items():
                    if 'file' in result and os.path.exists(result['file']):
                        download_results[download_id] = result
                        logger.debug(f"Restored download result: {download_id}")
                    else:
                        logger.debug(f"Skipped restoring missing file for: {download_id}")
    except Exception as e:
        logger.error(f"Error loading stored download results: {str(e)}")

# Save download results to disk
def save_download_results():
    try:
        with open(DOWNLOAD_RESULTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(download_results, f, ensure_ascii=False, indent=4)
        logger.debug(f"Saved download results to disk: {len(download_results)} entries")
    except Exception as e:
        logger.error(f"Error saving download results: {str(e)}")

# Load stored results on startup
load_download_results()

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
    filename = filename[:100]
    # Transliterate non-ASCII characters to ASCII equivalents where possible
    # For languages like Hebrew or Chinese that have no ASCII equivalent, this will remove them
    try:
        safe_filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
        # If transliteration removed everything or almost everything, use original with a prefix
        if len(safe_filename.strip()) < len(filename) * 0.3:
            return "download_" + str(int(time.time()))
        return safe_filename
    except:
        # If any error occurs, use a default filename
        return "download_" + str(int(time.time()))

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
            
            # Save updated download results to disk
            save_download_results()
            
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
    
    # Check if the file exists
    if not os.path.exists(file_path):
        return jsonify({
            'status': 'error',
            'message': 'Audio file not found on the server. It may have been deleted.'
        }), 404
    
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
    """Remove files older than 24 hours and not in use"""
    while True:
        time.sleep(3600)  # Run every hour
        try:
            current_time = time.time()
            for download_folder in os.listdir(TEMP_DIR):
                folder_path = os.path.join(TEMP_DIR, download_folder)
                if os.path.isdir(folder_path):
                    download_id = os.path.basename(folder_path)
                    
                    # Skip folders that are still tracked in download_results
                    if download_id in download_results:
                        logger.debug(f"Skipping cleanup of folder in use: {folder_path}")
                        continue
                    
                    # Check folder creation time
                    creation_time = os.path.getctime(folder_path)
                    if current_time - creation_time > 86400:  # Older than 24 hours (24*3600)
                        import shutil
                        shutil.rmtree(folder_path, ignore_errors=True)
                        logger.debug(f"Cleaned up old folder: {folder_path}")
        except Exception as e:
            logger.error(f"Error during auto cleanup: {str(e)}")

# Start the cleanup thread
threading.Thread(target=cleanup_old_files, daemon=True).start()

# Transcription related functions and routes
def format_time(seconds):
    """Format seconds to SRT timestamp format (HH:MM:SS,mmm)"""
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def extract_plain_text(transcription_data):
    """Extract plain text without timestamps from ElevenLabs transcription data"""
    # Extract all words from the transcription
    words = [w for w in transcription_data.get('words', []) if w.get('type') == 'word']
    
    # Group words into paragraphs (10 words per paragraph)
    paragraphs = []
    
    for i in range(0, len(words), 10):
        group = words[i:i+10]
        if not group:
            continue
            
        # Create text content from the words with spaces between them
        text_parts = []
        for j, word in enumerate(group):
            word_text = word.get('text', '')
            
            # Check if this is a spacing type or if we need to add a space
            if j > 0 and not word_text.startswith((' ', '.', ',', '!', '?', ':', ';')):
                # Add space before this word if it doesn't start with punctuation
                text_parts.append(' ')
            
            text_parts.append(word_text)
            
        paragraphs.append("".join(text_parts).strip())
    
    # Join paragraphs with line breaks
    return "\n\n".join(paragraphs)

def create_srt_content(transcription_data):
    """Create SRT file content from ElevenLabs transcription data"""
    srt_content = ""
    subtitle_index = 1
    
    # Extract words from the transcription
    words = [w for w in transcription_data.get('words', []) if w.get('type') == 'word']
    
    # Group words into subtitles (max 10 words per subtitle)
    for i in range(0, len(words), 10):
        group = words[i:i+10]
        if not group:
            continue
            
        start_time = group[0].get('start', 0)
        end_time = group[-1].get('end', start_time + 2)  # Default to 2 seconds after start if no end time
        
        # Create text content from the words with spaces between them
        # Using a space between each word
        text_parts = []
        for j, word in enumerate(group):
            word_text = word.get('text', '')
            
            # Check if this is a spacing type or if we need to add a space
            if j > 0 and not word_text.startswith((' ', '.', ',', '!', '?', ':', ';')):
                # Add space before this word if it doesn't start with punctuation
                text_parts.append(' ')
            
            text_parts.append(word_text)
            
        text = "".join(text_parts)
        
        # We'll skip adding speaker info as per user's request
        # speaker = group[0].get('speaker_id')
        # if speaker:
        #     text = f"[{speaker}] {text}"
            
        # Format subtitle entry
        srt_content += f"{subtitle_index}\n"
        srt_content += f"{format_time(start_time)} --> {format_time(end_time)}\n"
        srt_content += f"{text.strip()}\n\n"
        
        subtitle_index += 1
        
    return srt_content

@app.route('/transcribe/<download_id>', methods=['POST'])
def transcribe(download_id):
    """Transcribe the downloaded audio file using ElevenLabs API"""
    if download_id not in download_results:
        return jsonify({
            'status': 'error',
            'message': 'Audio file not found'
        }), 404
        
    result = download_results[download_id]
    
    if result['status'] != 'success':
        return jsonify({
            'status': 'error',
            'message': 'Audio file not available'
        }), 400
        
    # Get the API key from request
    api_key = request.form.get('api_key')
    if not api_key:
        return jsonify({
            'status': 'error',
            'message': 'ElevenLabs API key is required'
        }), 400
        
    # Get transcription options
    diarize = request.form.get('diarize', 'false').lower() == 'true'
    tag_events = request.form.get('tag_events', 'false').lower() == 'true'
    
    # Get file path
    file_path = result['file']
    
    # Check if the file exists
    if not os.path.exists(file_path):
        return jsonify({
            'status': 'error',
            'message': f'Audio file not found at: {file_path}. The file may have been deleted or moved.'
        }), 404
    
    try:
        # Prepare the API request to ElevenLabs
        url = "https://api.elevenlabs.io/v1/speech-to-text"
        
        headers = {
            "xi-api-key": api_key,
            # We don't set Content-Type, requests will set it automatically with boundary
        }
        
        # Open file in binary mode
        with open(file_path, 'rb') as audio_file:
            files = {
                'file': ('audio.mp3', audio_file, 'audio/mpeg')
            }
            
            data = {
                'model_id': 'scribe_v1',
                'diarize': str(diarize).lower(),  # Convert to 'true' or 'false'
                'tag_audio_events': str(tag_events).lower(),
                'timestamps_granularity': 'word'
            }
            
            logger.debug(f"Sending ElevenLabs API request with params: {data}")
            
            # Make the API request
            response = requests.post(url, headers=headers, files=files, data=data)
        
        # Check if the request was successful
        if response.status_code == 200:
            transcription_data = response.json()
            logger.debug(f"Received transcription data: {transcription_data}")
            
            # Create SRT file content
            srt_content = create_srt_content(transcription_data)
            
            # Extract plain text without timestamps
            plain_text = extract_plain_text(transcription_data)
            
            # Save SRT file
            title = result.get('title', 'transcription')
            srt_file_path = f"{TEMP_DIR}/{download_id}/{clean_filename(title)}.srt"
            
            with open(srt_file_path, 'w', encoding='utf-8') as srt_file:
                srt_file.write(srt_content)
                
            # Save TXT file
            txt_file_path = f"{TEMP_DIR}/{download_id}/{clean_filename(title)}.txt"
            
            with open(txt_file_path, 'w', encoding='utf-8') as txt_file:
                txt_file.write(plain_text)
            
            logger.debug(f"Created SRT file at: {srt_file_path}")
            logger.debug(f"Created TXT file at: {txt_file_path}")
            
            # Update download results to include transcription files
            download_results[download_id]['srt_file'] = srt_file_path
            download_results[download_id]['txt_file'] = txt_file_path
            download_results[download_id]['transcription_data'] = transcription_data
            
            # Return success response with transcription data
            return jsonify({
                'status': 'success',
                'text': plain_text,
                'srt_preview': srt_content,
                'plain_text': plain_text,
                'language': transcription_data.get('language_code', 'en')
            })
        else:
            # Handle API error
            error_message = "Error from ElevenLabs API"
            response_text = response.text
            logger.error(f"ElevenLabs API error. Status code: {response.status_code}, Response: {response_text}")
            
            try:
                error_data = response.json()
                error_message = error_data.get('detail', {}).get('message', error_message)
            except Exception as e:
                logger.error(f"Failed to parse error response: {str(e)}")
                
            return jsonify({
                'status': 'error',
                'message': error_message,
                'code': response.status_code
            }), 400
            
    except Exception as e:
        logger.error(f"Error during transcription: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/get_srt/<download_id>')
def get_srt(download_id):
    """Send the transcription SRT file to the user"""
    if download_id not in download_results:
        return jsonify({
            'status': 'error',
            'message': 'Transcription not found'
        }), 404
    
    result = download_results[download_id]
    
    if 'srt_file' not in result:
        return jsonify({
            'status': 'error',
            'message': 'SRT file not available'
        }), 400
    
    # Get the file path
    file_path = result['srt_file']
    title = result.get('title', 'transcription')
    
    # Check if the file exists
    if not os.path.exists(file_path):
        return jsonify({
            'status': 'error',
            'message': 'SRT file not found on the server. It may have been deleted.'
        }), 404
    
    # Send the file
    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"{clean_filename(title)}.srt",
        mimetype="text/srt"
    )

@app.route('/get_txt/<download_id>')
def get_txt(download_id):
    """Send the transcription TXT file to the user"""
    if download_id not in download_results:
        return jsonify({
            'status': 'error',
            'message': 'Transcription not found'
        }), 404
    
    result = download_results[download_id]
    
    if 'txt_file' not in result:
        return jsonify({
            'status': 'error',
            'message': 'TXT file not available'
        }), 400
    
    # Get the file path
    file_path = result['txt_file']
    title = result.get('title', 'transcription')
    
    # Check if the file exists
    if not os.path.exists(file_path):
        return jsonify({
            'status': 'error',
            'message': 'TXT file not found on the server. It may have been deleted.'
        }), 404
    
    # Send the file
    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"{clean_filename(title)}.txt",
        mimetype="text/plain"
    )
