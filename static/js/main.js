document.addEventListener('DOMContentLoaded', function() {
    // Get references to elements
    const downloadForm = document.getElementById('download-form');
    const youtubeUrlInput = document.getElementById('youtube-url');
    const downloadButton = document.getElementById('download-button');
    const progressSection = document.getElementById('progress-section');
    const progressBar = document.getElementById('progress-bar');
    const progressPercentage = document.getElementById('progress-percentage');
    const statusText = document.getElementById('status-text');
    const downloadCompleteSection = document.getElementById('download-complete-section');
    const downloadErrorSection = document.getElementById('download-error-section');
    const errorMessage = document.getElementById('error-message');
    const downloadFileButton = document.getElementById('download-file-button');
    const tryAgainButton = document.getElementById('try-again-button');
    const instructionsCard = document.getElementById('instructions-card');
    const downloadTitle = document.getElementById('download-title');
    
    // Transcription elements
    const transcribeButton = document.getElementById('transcribe-button');
    const transcribeModal = new bootstrap.Modal(document.getElementById('transcribeModal'));
    const transcriptionResultsModal = new bootstrap.Modal(document.getElementById('transcriptionResultsModal'));
    const elevenlabsApiKey = document.getElementById('elevenlabs-api-key');
    const diarizeOption = document.getElementById('diarize-option');
    const tagEventsOption = document.getElementById('tag-events-option');
    const startTranscriptionButton = document.getElementById('start-transcription-button');
    const transcriptionStatus = document.getElementById('transcription-status');
    const transcriptionStatusText = document.getElementById('transcription-status-text');
    const transcriptionPreview = document.getElementById('transcription-preview');
    const downloadSrtButton = document.getElementById('download-srt-button');

    // Current download ID
    let currentDownloadId = null;
    let progressInterval = null;

    // Form submission handler
    downloadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Get YouTube URL
        const youtubeUrl = youtubeUrlInput.value.trim();
        
        // Validate URL
        if (!isValidYoutubeUrl(youtubeUrl)) {
            showError('Please enter a valid YouTube URL');
            return;
        }
        
        // Start download process
        startDownload(youtubeUrl);
    });

    // Try again button handler
    tryAgainButton.addEventListener('click', function() {
        resetUI();
    });

    // Function to check if a URL is a valid YouTube URL
    function isValidYoutubeUrl(url) {
        // Simple validation, the server will do a more thorough check
        return url.includes('youtube.com/') || url.includes('youtu.be/');
    }

    // Function to start the download process
    function startDownload(youtubeUrl) {
        // Disable form and show progress section
        downloadButton.disabled = true;
        downloadButton.innerHTML = '<i class="fa fa-spinner fa-spin me-2"></i>Processing...';
        progressSection.classList.remove('d-none');
        instructionsCard.classList.add('d-none');
        
        // Reset UI elements
        progressBar.style.width = '0%';
        progressPercentage.textContent = '0%';
        statusText.textContent = 'Starting download...';
        downloadCompleteSection.classList.add('d-none');
        downloadErrorSection.classList.add('d-none');
        
        // Create form data
        const formData = new FormData();
        formData.append('youtube_url', youtubeUrl);
        
        // Send request to server
        fetch('/download', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'started') {
                // Store download ID and start progress tracking
                currentDownloadId = data.download_id;
                startProgressTracking(currentDownloadId);
            } else {
                showError(data.message || 'Failed to start download');
            }
        })
        .catch(error => {
            console.error('Error starting download:', error);
            showError('Network error, please try again');
        });
    }

    // Function to track download progress
    function startProgressTracking(downloadId) {
        // Clear any existing interval
        if (progressInterval) {
            clearInterval(progressInterval);
        }
        
        // Set up progress tracking interval
        progressInterval = setInterval(() => {
            fetch(`/progress/${downloadId}`)
                .then(response => response.json())
                .then(data => {
                    // Update progress bar
                    const progress = Math.round(data.progress);
                    progressBar.style.width = `${progress}%`;
                    progressPercentage.textContent = `${progress}%`;
                    
                    // Update status message
                    if (data.status === 'downloading') {
                        statusText.textContent = 'Downloading and processing audio...';
                    }
                    
                    // Check if download is finished
                    if (data.finished) {
                        clearInterval(progressInterval);
                        
                        if (data.status === 'success') {
                            downloadComplete(downloadId, data.title);
                        } else {
                            showError(data.message || 'Download failed');
                        }
                    }
                })
                .catch(error => {
                    console.error('Error tracking progress:', error);
                    clearInterval(progressInterval);
                    showError('Error tracking progress, please try again');
                });
        }, 1000);
    }

    // Function to handle download completion
    function downloadComplete(downloadId, title) {
        // Update UI
        statusText.textContent = 'Download completed successfully!';
        
        // Show download button
        downloadCompleteSection.classList.remove('d-none');
        
        // Set title
        if (title) {
            downloadTitle.textContent = `"${title}" is ready for download`;
        }
        
        // Set up download button
        downloadFileButton.onclick = function() {
            // Redirect to download URL
            window.location.href = `/get_file/${downloadId}`;
            
            // Cleanup after 2 seconds
            setTimeout(() => {
                cleanupDownload(downloadId);
            }, 2000);
        };
    }

    // Function to show error message
    function showError(message) {
        statusText.textContent = 'Error occurred';
        downloadErrorSection.classList.remove('d-none');
        errorMessage.textContent = message;
        
        // Enable form again
        downloadButton.disabled = false;
        downloadButton.innerHTML = '<i class="fa fa-download me-2"></i>Download Audio';
        
        // Clear interval if it exists
        if (progressInterval) {
            clearInterval(progressInterval);
        }
    }

    // Function to reset UI
    function resetUI() {
        // Hide progress section and show instructions
        progressSection.classList.add('d-none');
        instructionsCard.classList.remove('d-none');
        
        // Reset form
        downloadButton.disabled = false;
        downloadButton.innerHTML = '<i class="fa fa-download me-2"></i>Download Audio';
        
        // Clean up if there was a download
        if (currentDownloadId) {
            cleanupDownload(currentDownloadId);
            currentDownloadId = null;
        }
        
        // Clear interval if it exists
        if (progressInterval) {
            clearInterval(progressInterval);
        }
    }

    // Function to cleanup download
    function cleanupDownload(downloadId) {
        const formData = new FormData();
        formData.append('download_id', downloadId);
        
        fetch('/cleanup', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            console.log('Cleanup status:', data.status);
        })
        .catch(error => {
            console.error('Error during cleanup:', error);
        });
    }
    
    // Initialize API key input from localStorage if available
    if (elevenlabsApiKey) {
        const savedApiKey = localStorage.getItem('elevenlabs_api_key');
        if (savedApiKey) {
            elevenlabsApiKey.value = savedApiKey;
        }
    }
    
    // Add function to clear API key
    const clearApiKeyButton = document.getElementById('clear-api-key');
    if (clearApiKeyButton) {
        clearApiKeyButton.addEventListener('click', function() {
            // Clear the input field
            if (elevenlabsApiKey) {
                elevenlabsApiKey.value = '';
            }
            
            // Remove the key from localStorage
            localStorage.removeItem('elevenlabs_api_key');
            
            // Show confirmation message
            alert('Your API key has been removed from browser storage.');
        });
    }
    
    // Transcription functionality
    if (transcribeButton) {
        transcribeButton.addEventListener('click', function() {
            transcribeModal.show();
        });
    }
    
    if (startTranscriptionButton) {
        startTranscriptionButton.addEventListener('click', function() {
            const apiKey = elevenlabsApiKey.value.trim();
            
            if (!apiKey) {
                alert('Please enter your ElevenLabs API key');
                return;
            }
            
            // Save API key to localStorage
            localStorage.setItem('elevenlabs_api_key', apiKey);
            
            // Show status
            transcriptionStatus.classList.remove('d-none');
            startTranscriptionButton.disabled = true;
            
            // Prepare form data
            const formData = new FormData();
            formData.append('api_key', apiKey);
            formData.append('diarize', diarizeOption.checked);
            formData.append('tag_events', tagEventsOption.checked);
            
            // Make API request
            fetch(`/transcribe/${currentDownloadId}`, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // Hide the transcription modal
                transcribeModal.hide();
                startTranscriptionButton.disabled = false;
                transcriptionStatus.classList.add('d-none');
                
                if (data.status === 'success') {
                    // Show results modal
                    transcriptionPreview.textContent = data.srt_preview || data.text || 'Transcription completed successfully';
                    transcriptionResultsModal.show();
                    
                    // Set up download button
                    downloadSrtButton.onclick = function() {
                        window.location.href = `/get_srt/${currentDownloadId}`;
                    };
                } else {
                    alert(`Transcription failed: ${data.message || 'Unknown error'}`);
                }
            })
            .catch(error => {
                console.error('Error during transcription:', error);
                transcribeModal.hide();
                startTranscriptionButton.disabled = false;
                transcriptionStatus.classList.add('d-none');
                alert('Error communicating with the server. Please try again.');
            });
        });
    }
});
