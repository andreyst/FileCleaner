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
    filename = secure_filename(file.filename)
    if process_filename:
        for s in strings_to_remove:
            filename = filename.replace(s, '')
    
    # Read file content as binary
    content = file.read()
    
    # Only process text if strings need to be removed
    if strings_to_remove:
        try:
            # Try to decode as text if strings need to be removed
            text_content = content.decode('utf-8')
            for s in strings_to_remove:
                text_content = text_content.replace(s, '')
            content = text_content.encode('utf-8')
        except UnicodeDecodeError:
            # If file is binary, skip string replacement
            pass
    
    # Upload to S3
    s3.put_object(
        Bucket=os.getenv('S3_BUCKET'),
        Key=filename,
        Body=content
    )
    
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
