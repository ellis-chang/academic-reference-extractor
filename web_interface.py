#!/usr/bin/env python3
"""
Simple Web Interface for Reference Extractor
Provides a basic Flask web UI for uploading PDFs and downloading results

Usage:
    python web_interface.py
    
Then open http://localhost:5000 in your browser
"""

import os
import uuid
import threading
from datetime import datetime
from flask import Flask, render_template_string, request, send_file, jsonify, redirect, url_for
from werkzeug.utils import secure_filename

# Import the main processing function
from main import process_references

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/reference_extractor_uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Track processing jobs
jobs = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reference Extractor</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .upload-area {
            border: 2px dashed #ddd;
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            transition: all 0.3s;
            cursor: pointer;
        }
        .upload-area:hover, .upload-area.dragover {
            border-color: #667eea;
            background: #f8f9ff;
        }
        .upload-icon {
            font-size: 48px;
            margin-bottom: 15px;
        }
        input[type="file"] {
            display: none;
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .options {
            margin: 25px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .option-row {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }
        .option-row:last-child {
            margin-bottom: 0;
        }
        .option-row label {
            margin-left: 10px;
            color: #555;
        }
        .progress-container {
            display: none;
            margin-top: 25px;
        }
        .progress-bar {
            height: 8px;
            background: #eee;
            border-radius: 4px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
        }
        .status {
            margin-top: 10px;
            font-size: 14px;
            color: #666;
        }
        .result {
            display: none;
            margin-top: 25px;
            padding: 20px;
            background: #e8f5e9;
            border-radius: 8px;
            text-align: center;
        }
        .result.error {
            background: #ffebee;
        }
        .download-btn {
            background: #4caf50;
            margin-top: 15px;
        }
        .file-name {
            margin-top: 15px;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 6px;
            font-size: 14px;
            color: #333;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>📚 Reference Extractor</h1>
            <p class="subtitle">Extract author affiliations and contact details from academic PDFs</p>
            
            <form id="uploadForm" enctype="multipart/form-data">
                <div class="upload-area" id="dropZone" onclick="document.getElementById('fileInput').click()">
                    <div class="upload-icon">📄</div>
                    <p><strong>Drop PDF here</strong> or click to browse</p>
                    <p style="font-size: 12px; color: #999; margin-top: 10px;">Max file size: 50MB</p>
                </div>
                <input type="file" id="fileInput" name="pdf_file" accept=".pdf">
                <div class="file-name" id="fileName" style="display: none;"></div>
                
                <div class="options">
                    <div class="option-row">
                        <input type="checkbox" id="useLlm" name="use_llm" checked>
                        <label for="useLlm">Use AI for enhanced extraction (recommended)</label>
                    </div>
                    <div class="option-row">
                        <input type="checkbox" id="exportCsv" name="export_csv">
                        <label for="exportCsv">Also export as CSV</label>
                    </div>
                </div>
                
                <button type="submit" class="btn" id="submitBtn">Extract Author Information</button>
            </form>
            
            <div class="progress-container" id="progressContainer">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <p class="status" id="statusText">Processing...</p>
            </div>
            
            <div class="result" id="resultContainer">
                <p id="resultText"></p>
                <a id="downloadLink" href="#" class="btn download-btn" style="display: inline-block; text-decoration: none;">
                    ⬇️ Download Excel File
                </a>
            </div>
        </div>
    </div>
    
    <script>
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const fileName = document.getElementById('fileName');
        const form = document.getElementById('uploadForm');
        const submitBtn = document.getElementById('submitBtn');
        const progressContainer = document.getElementById('progressContainer');
        const progressFill = document.getElementById('progressFill');
        const statusText = document.getElementById('statusText');
        const resultContainer = document.getElementById('resultContainer');
        const resultText = document.getElementById('resultText');
        const downloadLink = document.getElementById('downloadLink');
        
        // Drag and drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'));
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'));
        });
        
        dropZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length) {
                fileInput.files = files;
                showFileName(files[0].name);
            }
        });
        
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) {
                showFileName(fileInput.files[0].name);
            }
        });
        
        function showFileName(name) {
            fileName.textContent = '📎 ' + name;
            fileName.style.display = 'block';
        }
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            if (!fileInput.files.length) {
                alert('Please select a PDF file first.');
                return;
            }
            
            const formData = new FormData();
            formData.append('pdf_file', fileInput.files[0]);
            formData.append('use_llm', document.getElementById('useLlm').checked);
            formData.append('export_csv', document.getElementById('exportCsv').checked);
            
            submitBtn.disabled = true;
            progressContainer.style.display = 'block';
            resultContainer.style.display = 'none';
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Poll for status
                    pollStatus(result.job_id);
                } else {
                    showError(result.error);
                }
            } catch (error) {
                showError(error.message);
            }
        });
        
        async function pollStatus(jobId) {
            try {
                const response = await fetch('/status/' + jobId);
                const status = await response.json();
                
                progressFill.style.width = status.progress + '%';
                statusText.textContent = status.message;
                
                if (status.status === 'complete') {
                    showSuccess(status.output_file);
                } else if (status.status === 'error') {
                    showError(status.error);
                } else {
                    setTimeout(() => pollStatus(jobId), 1000);
                }
            } catch (error) {
                showError(error.message);
            }
        }
        
        function showSuccess(outputFile) {
            submitBtn.disabled = false;
            progressContainer.style.display = 'none';
            resultContainer.style.display = 'block';
            resultContainer.classList.remove('error');
            resultText.textContent = '✅ Extraction complete!';
            downloadLink.href = '/download/' + outputFile;
            downloadLink.style.display = 'inline-block';
        }
        
        function showError(message) {
            submitBtn.disabled = false;
            progressContainer.style.display = 'none';
            resultContainer.style.display = 'block';
            resultContainer.classList.add('error');
            resultText.textContent = '❌ Error: ' + message;
            downloadLink.style.display = 'none';
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/upload', methods=['POST'])
def upload():
    if 'pdf_file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})
    
    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'error': 'Only PDF files are allowed'})
    
    # Save uploaded file
    job_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
    file.save(upload_path)
    
    # Get options
    use_llm = request.form.get('use_llm', 'false').lower() == 'true'
    export_csv = request.form.get('export_csv', 'false').lower() == 'true'
    
    # Initialize job
    jobs[job_id] = {
        'status': 'processing',
        'progress': 0,
        'message': 'Starting...',
        'input_file': upload_path,
        'output_file': None,
        'error': None
    }
    
    # Process in background
    thread = threading.Thread(
        target=process_job,
        args=(job_id, upload_path, use_llm, export_csv)
    )
    thread.start()
    
    return jsonify({'success': True, 'job_id': job_id})


def process_job(job_id: str, input_path: str, use_llm: bool, export_csv: bool):
    try:
        jobs[job_id]['message'] = 'Parsing PDF...'
        jobs[job_id]['progress'] = 10
        
        # Generate output path
        output_filename = f"{job_id}_output.xlsx"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        jobs[job_id]['message'] = 'Extracting author information...'
        jobs[job_id]['progress'] = 30
        
        # Process
        process_references(
            pdf_path=input_path,
            output_path=output_path,
            use_llm=use_llm,
            verbose=False
        )
        
        jobs[job_id]['progress'] = 100
        jobs[job_id]['status'] = 'complete'
        jobs[job_id]['message'] = 'Complete!'
        jobs[job_id]['output_file'] = output_filename
        
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)


@app.route('/status/<job_id>')
def get_status(job_id):
    if job_id not in jobs:
        return jsonify({'status': 'error', 'error': 'Job not found'})
    return jsonify(jobs[job_id])


@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(
            file_path,
            as_attachment=True,
            download_name='extracted_authors.xlsx'
        )
    return 'File not found', 404


if __name__ == '__main__':
    print("\n" + "="*50)
    print("  Reference Extractor Web Interface")
    print("="*50)
    print("\n  Open http://localhost:5000 in your browser")
    print("  Press Ctrl+C to stop the server\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
