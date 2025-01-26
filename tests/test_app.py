import pytest
from io import BytesIO
from pathlib import Path
import zipfile
import tempfile

def test_homepage(client):
    """Test that homepage loads correctly"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Upload and Clean Files' in response.data
    assert b'max 10MB' in response.data  # Test against test configuration

def test_upload_without_file(client):
    """Test upload without file"""
    response = client.post('/', follow_redirects=True)
    assert response.status_code == 400
    assert b'No files uploaded' in response.data

def test_process_file_content(client, mock_s3_bucket, sample_epub):
    """Test processing file content"""
    data = {
        'files': (BytesIO(sample_epub), 'test.epub'),
        'strings': ['REMOVE_THIS'],
        'process_filename': 'true'
    }
    response = client.post('/?process=true', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    assert b'Files Processed Successfully' in response.data
    assert b'test.epub' in response.data
    assert b'Download' in response.data

def test_process_filename(client, mock_s3_bucket, sample_epub):
    """Test processing filename"""
    data = {
        'files': (BytesIO(sample_epub), 'REMOVE_THIS_test.epub'),
        'strings': ['REMOVE_THIS'],
        'process_filename': 'true'
    }
    response = client.post('/?process=true', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    assert b'_test.epub' in response.data
    assert b'REMOVE_THIS' not in response.data

def test_file_size_limit(client):
    """Test file size limit"""
    # Create a file larger than test MAX_CONTENT_LENGTH (10MB)
    large_file = BytesIO(b'PK\x03\x04' + b'x' * (11 * 1024 * 1024))  # 11MB file with ZIP header
    data = {
        'files': (large_file, 'large.epub'),
        'strings': ['test']
    }
    response = client.post('/?process=true', data=data, content_type='multipart/form-data')
    assert response.status_code == 413  # Request Entity Too Large

def test_multiple_files(client, mock_s3_bucket, sample_epub):
    """Test uploading multiple files"""
    data = {
        'files': [
            (BytesIO(sample_epub), 'test1.epub'),
            (BytesIO(sample_epub), 'test2.epub')
        ],
        'strings': ['REMOVE_THIS']
    }
    response = client.post('/?process=true', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    assert b'test1.epub' in response.data
    assert b'test2.epub' in response.data

def test_multiple_strings(client, mock_s3_bucket, sample_epub):
    """Test removing multiple strings"""
    data = {
        'files': (BytesIO(sample_epub), 'test.epub'),
        'strings': ['REMOVE_THIS', 'text']
    }
    response = client.post('/?process=true', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    assert b'test.epub' in response.data
