import pytest
import os
import tempfile
from pathlib import Path
import zipfile
import boto3
from moto import mock_aws
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB for testing
    app.config['MAX_FILE_SIZE_MB'] = 10  # Set MAX_FILE_SIZE_MB to match test configuration
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_s3_bucket():
    with mock_aws():
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
