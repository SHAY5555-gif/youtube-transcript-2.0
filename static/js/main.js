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
});
