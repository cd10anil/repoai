"""
Functional Test Suite
Tests for core application functionality.
Run with: pytest tests/functional/ -v
"""
import pytest
import os
import sys
import json
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app_secure import app, API_KEY, get_code_files


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers():
    """Provide authentication headers"""
    return {"Authorization": f"Bearer {API_KEY}"}


@pytest.fixture
def temp_project():
    """Create temporary project structure for testing"""
    temp_dir = tempfile.mkdtemp()
    
    # Create sample files
    with open(os.path.join(temp_dir, 'test.py'), 'w') as f:
        f.write('def hello():\n    return "world"\n')
    
    with open(os.path.join(temp_dir, 'test.js'), 'w') as f:
        f.write('function hello() {\n    return "world";\n}\n')
    
    with open(os.path.join(temp_dir, 'README.md'), 'w') as f:
        f.write('# Test Project\n')
    
    # Create subdirectory
    sub_dir = os.path.join(temp_dir, 'src')
    os.makedirs(sub_dir)
    with open(os.path.join(sub_dir, 'app.py'), 'w') as f:
        f.write('print("Hello")\n')
    
    yield temp_dir
    shutil.rmtree(temp_dir)


# =============================================================================
# Health Check Tests
# =============================================================================
class TestHealthCheck:
    """Test health endpoint"""
    
    def test_health_returns_200(self, client):
        """Health endpoint should return 200 OK"""
        response = client.get('/health')
        assert response.status_code == 200
    
    def test_health_returns_healthy_status(self, client):
        """Health endpoint should return healthy status"""
        response = client.get('/health')
        data = response.get_json()
        assert data['status'] == 'healthy'
    
    def test_health_no_auth_required(self, client):
        """Health endpoint should not require authentication"""
        response = client.get('/health')
        assert response.status_code == 200


# =============================================================================
# API Key Retrieval Tests
# =============================================================================
class TestAPIKey:
    """Test API key endpoint"""
    
    def test_get_api_key_returns_200(self, client):
        """Should return API key"""
        response = client.get('/auth/key')
        assert response.status_code == 200
    
    def test_get_api_key_contains_key(self, client):
        """Response should contain API key"""
        response = client.get('/auth/key')
        data = response.get_json()
        assert 'api_key' in data
        assert len(data['api_key']) >= 32


# =============================================================================
# File Scanning Tests
# =============================================================================
class TestFileScanning:
    """Test folder scanning functionality"""
    
    def test_scan_folder_returns_files(self, client, auth_headers, temp_project):
        """Should return list of files"""
        response = client.post('/scan_folder',
                              json={'folder_path': temp_project},
                              headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'files' in data
        assert len(data['files']) > 0
    
    def test_scan_folder_includes_py_files(self, client, auth_headers, temp_project):
        """Should include Python files"""
        response = client.post('/scan_folder',
                              json={'folder_path': temp_project},
                              headers=auth_headers)
        data = response.get_json()
        py_files = [f for f in data['files'] if f.endswith('.py')]
        assert len(py_files) > 0
    
    def test_scan_folder_includes_js_files(self, client, auth_headers, temp_project):
        """Should include JavaScript files"""
        response = client.post('/scan_folder',
                              json={'folder_path': temp_project},
                              headers=auth_headers)
        data = response.get_json()
        js_files = [f for f in data['files'] if f.endswith('.js')]
        assert len(js_files) > 0
    
    def test_scan_folder_excludes_venv(self, client, auth_headers, temp_project):
        """Should exclude venv directories"""
        # Create venv directory
        venv_dir = os.path.join(temp_project, 'venv')
        os.makedirs(venv_dir)
        with open(os.path.join(venv_dir, 'test.py'), 'w') as f:
            f.write('# venv file\n')
        
        response = client.post('/scan_folder',
                              json={'folder_path': temp_project},
                              headers=auth_headers)
        data = response.get_json()
        venv_files = [f for f in data['files'] if 'venv' in f]
        assert len(venv_files) == 0, "venv files should be excluded"
    
    def test_scan_folder_excludes_node_modules(self, client, auth_headers, temp_project):
        """Should exclude node_modules directories"""
        # Create node_modules directory
        nm_dir = os.path.join(temp_project, 'node_modules')
        os.makedirs(nm_dir)
        with open(os.path.join(nm_dir, 'test.js'), 'w') as f:
            f.write('// node_modules file\n')
        
        response = client.post('/scan_folder',
                              json={'folder_path': temp_project},
                              headers=auth_headers)
        data = response.get_json()
        nm_files = [f for f in data['files'] if 'node_modules' in f]
        assert len(nm_files) == 0, "node_modules files should be excluded"
    
    def test_scan_folder_sorted_results(self, client, auth_headers, temp_project):
        """Should return sorted file list"""
        response = client.post('/scan_folder',
                              json={'folder_path': temp_project},
                              headers=auth_headers)
        data = response.get_json()
        assert data['files'] == sorted(data['files']), "Files should be sorted"
    
    def test_scan_folder_requires_auth(self, client, temp_project):
        """Should require authentication"""
        response = client.post('/scan_folder',
                              json={'folder_path': temp_project})
        assert response.status_code == 401
    
    def test_scan_folder_invalid_path(self, client, auth_headers):
        """Should reject invalid paths"""
        response = client.post('/scan_folder',
                              json={'folder_path': '/nonexistent/path'},
                              headers=auth_headers)
        assert response.status_code == 400


# =============================================================================
# get_code_files Unit Tests
# =============================================================================
class TestGetCodeFiles:
    """Test get_code_files helper function"""
    
    def test_returns_list(self, temp_project):
        """Should return a list"""
        result = get_code_files(temp_project)
        assert isinstance(result, list)
    
    def test_finds_python_files(self, temp_project):
        """Should find Python files"""
        result = get_code_files(temp_project)
        py_files = [f for f in result if f.endswith('.py')]
        assert len(py_files) > 0
    
    def test_finds_javascript_files(self, temp_project):
        """Should find JavaScript files"""
        result = get_code_files(temp_project)
        js_files = [f for f in result if f.endswith('.js')]
        assert len(js_files) > 0
    
    def test_excludes_hidden_directories(self, temp_project):
        """Should exclude hidden directories"""
        # Create hidden directory
        hidden_dir = os.path.join(temp_project, '.hidden')
        os.makedirs(hidden_dir)
        with open(os.path.join(hidden_dir, 'test.py'), 'w') as f:
            f.write('# hidden\n')
        
        result = get_code_files(temp_project)
        hidden_files = [f for f in result if '.hidden' in f]
        assert len(hidden_files) == 0
    
    def test_handles_nonexistent_path(self):
        """Should handle non-existent path gracefully"""
        result = get_code_files('/nonexistent/path')
        assert result == []
    
    def test_returns_relative_paths(self, temp_project):
        """Should return relative paths"""
        result = get_code_files(temp_project)
        for path in result:
            assert not os.path.isabs(path), f"Path should be relative: {path}"


# =============================================================================
# Abort Endpoint Tests
# =============================================================================
class TestAbortEndpoint:
    """Test abort functionality"""
    
    def test_abort_returns_200(self, client, auth_headers):
        """Abort should return 200"""
        response = client.post('/abort', headers=auth_headers)
        assert response.status_code == 200
    
    def test_abort_requires_auth(self, client):
        """Abort should require authentication"""
        response = client.post('/abort')
        assert response.status_code == 401
    
    def test_abort_returns_status(self, client, auth_headers):
        """Abort should return aborted status"""
        response = client.post('/abort', headers=auth_headers)
        data = response.get_json()
        assert data['status'] == 'aborted'


# =============================================================================
# Index Page Tests
# =============================================================================
class TestIndexPage:
    """Test index page"""
    
    def test_index_returns_200(self, client):
        """Index should return 200"""
        response = client.get('/')
        assert response.status_code == 200
    
    def test_index_no_auth_required(self, client):
        """Index should not require authentication"""
        response = client.get('/')
        assert response.status_code == 200


# =============================================================================
# Decision Endpoint Tests
# =============================================================================
class TestDecisionEndpoint:
    """Test decision endpoint"""
    
    def test_reject_returns_200(self, client, auth_headers):
        """Reject action should return 200"""
        response = client.post('/decision',
                              json={'action': 'REJECT'},
                              headers=auth_headers)
        assert response.status_code == 200
    
    def test_reject_returns_success(self, client, auth_headers):
        """Reject action should return success status"""
        response = client.post('/decision',
                              json={'action': 'REJECT'},
                              headers=auth_headers)
        data = response.get_json()
        assert data['status'] == 'success'
    
    def test_invalid_action_returns_400(self, client, auth_headers):
        """Invalid action should return 400"""
        response = client.post('/decision',
                              json={'action': 'INVALID'},
                              headers=auth_headers)
        assert response.status_code == 400
    
    def test_approve_without_file_returns_400(self, client, auth_headers):
        """Approve without active file should return 400"""
        response = client.post('/decision',
                              json={'action': 'APPROVE'},
                              headers=auth_headers)
        assert response.status_code == 400


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
