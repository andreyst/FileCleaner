import os
import tempfile
import shutil
import zipfile
from pathlib import Path
from flask import Flask, request, render_template, send_file
import boto3
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max file size

s3 = boto3.client('s3')

def get_signed_url(filename, expiration=3600):
    """Generate a signed URL for an S3 object that expires in 1 hour"""
    url = s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': os.getenv('S3_BUCKET'),
            'Key': filename
        },
        ExpiresIn=expiration
    )
    return url

def process_file(file, strings_to_remove, process_filename):
    print(f"\nProcessing EPUB file: {file.filename}")
    
    filename = secure_filename(file.filename)
    if process_filename:
        for s in strings_to_remove:
            filename = filename.replace(s, '')
        print(f"Processed filename: {filename}")
    
    # Create temporary directory for EPUB processing
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
        
        # Process text files
        text_extensions = {'.xhtml', '.html', '.htm', '.xml', '.css', '.txt', '.opf', '.ncx'}
        total_files = sum(1 for _ in Path(extract_dir).rglob('*') if Path(_).suffix.lower() in text_extensions)
        processed_files = 0
        
        for path in Path(extract_dir).rglob('*'):
            if path.suffix.lower() in text_extensions:
                processed_files += 1
                print(f"\nProcessing file {processed_files}/{total_files}: {path.name}")
                
                try:
                    # Read and process content
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Replace strings
                    if strings_to_remove:
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
                    
                    # Write processed content
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                except UnicodeDecodeError:
                    print(f"Skipping binary file: {path.name}")
                    continue
        
        # Create new EPUB
        print("\nCreating processed EPUB")
        with zipfile.ZipFile(processed_path, 'w', zipfile.ZIP_DEFLATED) as new_epub:
            for path in Path(extract_dir).rglob('*'):
                if path.is_file():
                    arcname = str(path.relative_to(extract_dir))
                    new_epub.write(path, arcname)
        
        # Upload to S3
        print(f"Uploading to S3: {filename}")
        with open(processed_path, 'rb') as f:
            s3.put_object(
                Bucket=os.getenv('S3_BUCKET'),
                Key=filename,
                Body=f.read()
            )
        print("Upload complete")
        
        # Generate signed URL and return
        signed_url = get_signed_url(filename)
        return filename, signed_url

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'files' not in request.files:
            return 'No files uploaded', 400
        
        files = request.files.getlist('files')
        strings_to_remove = request.form.getlist('strings')
        process_filename = 'process_filename' in request.form
        
        processed_files = []
        for file in files:
            if file.filename:
                filename, signed_url = process_file(file, strings_to_remove, process_filename)
                processed_files.append({'name': filename, 'url': signed_url})
        
        return render_template('result.html', processed_files=processed_files)
    
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(debug=True)
