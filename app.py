import os
from flask import Flask, request, render_template, send_file
import boto3
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max file size

s3 = boto3.client('s3')

def process_file(file, strings_to_remove, process_filename):
    print(f"\nProcessing file: {file.filename}")
    
    filename = secure_filename(file.filename)
    if process_filename:
        for s in strings_to_remove:
            filename = filename.replace(s, '')
        print(f"Processed filename: {filename}")
    
    # Read file content as binary
    content = file.read()
    print(f"Read {len(content)} bytes")
    
    # Only process text if strings need to be removed
    if strings_to_remove:
        try:
            # Try to decode as text if strings need to be removed
            text_content = content.decode('utf-8')
            print("File decoded as text, processing strings...")
            total_len = len(text_content)
            processed_len = 0
            last_percent = 0
            
            for s in strings_to_remove:
                text_content = text_content.replace(s, '')
                processed_len += len(s)
                percent = min(99, int((processed_len / total_len) * 100))
                if percent > last_percent:
                    print(f"Processing strings: {percent}%")
                    last_percent = percent
            
            content = text_content.encode('utf-8')
            print("String processing complete (100%)")
        except UnicodeDecodeError:
            print("Binary file detected, skipping string replacement")
            pass
    
    # Upload to S3
    print(f"Uploading to S3: {filename}")
    s3.put_object(
        Bucket=os.getenv('S3_BUCKET'),
        Key=filename,
        Body=content
    )
    print("Upload complete")
    
    return filename

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
                processed_filename = process_file(file, strings_to_remove, process_filename)
                processed_files.append(processed_filename)
        
        return render_template('result.html', processed_files=processed_files)
    
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(debug=True)
