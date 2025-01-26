import os
from flask import Flask, request, render_template, send_file
import boto3
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024  # 15MB max file size

s3 = boto3.client('s3')

def process_file(file, strings_to_remove, process_filename):
    filename = secure_filename(file.filename)
    if process_filename:
        for s in strings_to_remove:
            filename = filename.replace(s, '')
    
    # Read and process file content
    content = file.read()
    if isinstance(content, bytes):
        content = content.decode('utf-8')
    
    for s in strings_to_remove:
        content = content.replace(s, '')
    
    # Upload to S3
    s3.put_object(
        Bucket=os.getenv('S3_BUCKET'),
        Key=filename,
        Body=content.encode('utf-8')
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
