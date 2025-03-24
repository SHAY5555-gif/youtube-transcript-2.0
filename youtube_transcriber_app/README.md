# YouTube Video Transcriber App

This is a Flask-based web application that allows downloading audio from YouTube videos and transcribing them using ElevenLabs API.

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Run the app: `python main.py`
3. Open a browser at `http://localhost:5000`

## Required packages
- flask
- yt-dlp
- gunicorn
- requests
- psycopg2-binary
- flask-sqlalchemy
- email-validator

## Features
- Download audio from YouTube videos
- Transcribe audio using ElevenLabs API
- Support for SRT and TXT output formats
- Progress tracking for downloads
- Mobile-friendly responsive design

## Usage
1. Paste a YouTube URL into the input field
2. Click "Download Audio" to extract the audio
3. Once downloaded, click "Transcribe" to convert to text
4. Enter your ElevenLabs API key
5. View and download the transcription in TXT or SRT format

## Note
You'll need an ElevenLabs API key for the transcription functionality.