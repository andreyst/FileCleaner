import pytest
import os
import tempfile
from pathlib import Path
import zipfile
import boto3
from moto import mock_s3
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_s3_bucket():
    with mock_s3():
        s3 = boto3.client('s3')
        s3.create_bucket(Bucket='test-bucket')
        os.environ['S3_BUCKET'] = 'test-bucket'
        yield s3

@pytest.fixture
def sample_epub():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a simple EPUB structure
        epub_path = Path(temp_dir) / 'test.epub'
        content_path = Path(temp_dir) / 'content'
        content_path.mkdir()
        
        # Create sample content files
        (content_path / 'chapter1.xhtml').write_text(
            '<html><body>Test content with REMOVE_THIS text.</body></html>'
        )
        (content_path / 'style.css').write_text('body { color: REMOVE_THIS; }')
        
        # Create EPUB
        with zipfile.ZipFile(epub_path, 'w', zipfile.ZIP_DEFLATED) as epub:
            for file in content_path.rglob('*'):
                if file.is_file():
                    epub.write(file, str(file.relative_to(content_path)))
        
        with open(epub_path, 'rb') as f:
            yield f.read()
