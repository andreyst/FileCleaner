import os
import tempfile
import shutil
import zipfile
import uuid
from pathlib import Path
from flask import Flask, request, render_template, send_file
import boto3
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Get max file size from environment or use default
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 200))
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert MB to bytes
app.config['MAX_FILE_SIZE_MB'] = MAX_FILE_SIZE_MB  # Store in config for template access

s3 = boto3.client('s3')

def get_signed_url(s3_key, expiration=3600):
    """Generate a signed URL for an S3 object that expires in 1 hour"""
    url = s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': os.getenv('S3_BUCKET'),
            'Key': s3_key
        },
        ExpiresIn=expiration
    )
    return url

def process_text_content(content, strings_to_remove):
    """Process text content by removing specified strings"""
    if not strings_to_remove:
        return content
    
    total_len = len(content)
    processed_len = 0
    last_percent = 0
    
    for s in strings_to_remove:
        content = content.replace(s, '')
        processed_len += len(s)
        percent = min(99, int((processed_len / total_len) * 100))
        if percent > last_percent:
            print(f"Processing strings: {percent}%")
            last_percent = percent
    
    return content

def process_epub_file(extract_dir, strings_to_remove):
    """Process all text files in extracted EPUB directory"""
    text_extensions = {'.xhtml', '.html', '.htm', '.xml', '.css', '.txt', '.opf', '.ncx'}
    total_files = sum(1 for _ in Path(extract_dir).rglob('*') 
                     if Path(_).suffix.lower() in text_extensions)
    processed_files = 0
    
    for path in Path(extract_dir).rglob('*'):
        if path.suffix.lower() in text_extensions:
            processed_files += 1
            print(f"\nProcessing file {processed_files}/{total_files}: {path.name}")
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                content = process_text_content(content, strings_to_remove)
                
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
            except UnicodeDecodeError:
                print(f"Skipping binary file: {path.name}")
                continue

def create_processed_epub(extract_dir, output_path):
    """Create new EPUB from processed files"""
    print("\nCreating processed EPUB")
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as new_epub:
        for path in Path(extract_dir).rglob('*'):
            if path.is_file():
                arcname = str(path.relative_to(extract_dir))
                new_epub.write(path, arcname)

def upload_to_s3(file_path, s3_key):
    """Upload file to S3 and return signed URL"""
    print(f"Uploading to S3: {s3_key}")
    with open(file_path, 'rb') as f:
        s3.put_object(
            Bucket=os.getenv('S3_BUCKET'),
            Key=s3_key,
            Body=f.read()
        )
    print("Upload complete")
    return get_signed_url(s3_key)

def process_file(file, strings_to_remove, process_filename):
    """Main function to process uploaded EPUB file"""
    print(f"\nProcessing EPUB file: {file.filename}")
    
    # Create unique directory for this upload
    upload_id = str(uuid.uuid4())
    s3_dir = f"uploads/{upload_id}"
    
    filename = secure_filename(file.filename)
    if process_filename:
        for s in strings_to_remove:
            filename = filename.replace(s, '')
        print(f"Processed filename: {filename}")
    
    s3_key = f"{s3_dir}/{filename}"
    
    # Process file in temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        epub_path = os.path.join(temp_dir, 'original.epub')
        processed_path = os.path.join(temp_dir, filename)
        
        # Save uploaded file
        file.save(epub_path)
        print(f"Saved EPUB to temporary location")
        
        # Extract EPUB
        extract_dir = os.path.join(temp_dir, 'extracted')
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(epub_path, 'r') as epub:
            epub.extractall(extract_dir)
        print("Extracted EPUB contents")
        
        # Process EPUB contents
        process_epub_file(extract_dir, strings_to_remove)
        
        # Create new EPUB
        create_processed_epub(extract_dir, processed_path)
        
        # Upload and get URL
        signed_url = upload_to_s3(processed_path, s3_key)
        
        return filename, signed_url

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'files' not in request.files or not request.files.getlist('files')[0].filename:
            return 'No files uploaded', 400
        
        files = request.files.getlist('files')
        strings_to_remove = request.form.getlist('strings')
        process_filename = 'process_filename' in request.form
        
        processed_files = []
        for file in files:
            if file.filename:
                filename, signed_url = process_file(file, strings_to_remove, process_filename)
                processed_files.append({'name': filename, 'url': signed_url})
        
        return render_template('result.html', processed_files=processed_files, max_file_size_mb=MAX_FILE_SIZE_MB)
    
    return render_template('upload.html', max_file_size_mb=app.config['MAX_FILE_SIZE_MB'])

if __name__ == '__main__':
    app.run(debug=True)
