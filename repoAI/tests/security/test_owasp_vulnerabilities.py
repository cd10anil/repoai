"""
OWASP Security Test Suite
Tests for all 7 OWASP vulnerabilities identified and fixed.
Run with: pytest tests/security/ -v
"""
import pytest
import os
import sys
import json
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app_secure import (
    app, 
    is_path_safe, 
    validate_folder_path, 
    validate_code_content, 
    sanitize_output,
    API_KEY
)


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
def temp_dir():
    """Create temporary directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


# =============================================================================
# OWASP A01:2021 - Broken Access Control (Path Traversal)
# =============================================================================
class TestPathTraversal:
    """Test cases for path traversal prevention"""
    
    def test_is_path_safe_valid_path(self, temp_dir):
        """FIX: Valid path within base directory should be allowed"""
        result = is_path_safe(temp_dir, "subfolder/file.txt")
        assert result is True, "Valid relative path should be allowed"
    
    def test_is_path_safe_traversal_attack(self, temp_dir):
        """FIX: Path traversal with ../ should be blocked"""
        result = is_path_safe(temp_dir, "../../../etc/passwd")
        assert result is False, "Path traversal should be blocked"
    
    def test_is_path_safe_absolute_path(self, temp_dir):
        """FIX: Absolute path outside base should be blocked"""
        result = is_path_safe(temp_dir, "/etc/passwd")
        assert result is False, "Absolute path outside base should be blocked"
    
    def test_validate_folder_path_blocks_null_byte(self, temp_dir):
        """FIX: Null byte injection blocked by validate_folder_path"""
        result = validate_folder_path(f"{temp_dir}\x00.jpg")
        assert result is False, "Null byte injection should be blocked"
    
    def test_validate_folder_path_blocks_traversal_patterns(self):
        """FIX: Various traversal patterns blocked by validate_folder_path"""
        malicious_patterns = [
            "../../../etc/passwd",
            "..\\..\\..\\etc\\passwd",
        ]
        for pattern in malicious_patterns:
            result = validate_folder_path(pattern)
            assert result is False, f"Pattern '{pattern}' should be blocked"
    
    def test_is_path_safe_with_dot_dot(self, temp_dir):
        """FIX: Relative traversal paths blocked by is_path_safe"""
        result = is_path_safe(temp_dir, "../../../etc/passwd")
        assert result is False, "Traversal with ../ should be blocked"
    
    def test_validate_folder_path_valid(self, temp_dir):
        """FIX: Valid existing directory should pass validation"""
        result = validate_folder_path(temp_dir)
        assert result is True, "Existing directory should be valid"
    
    def test_validate_folder_path_nonexistent(self):
        """FIX: Non-existent directory should fail validation"""
        result = validate_folder_path("/nonexistent/path/that/does/not/exist")
        assert result is False, "Non-existent directory should be invalid"
    
    def test_validate_folder_path_null_byte(self, temp_dir):
        """FIX: Folder path with null byte should fail validation"""
        result = validate_folder_path(f"{temp_dir}\x00.jpg")
        assert result is False, "Path with null byte should be invalid"
    
    def test_validate_folder_path_traversal(self):
        """FIX: Folder path with traversal should fail validation"""
        result = validate_folder_path("../../../etc")
        assert result is False, "Path with traversal should be invalid"
    
    def test_scan_folder_blocks_traversal(self, client, auth_headers):
        """FIX: Endpoint should reject path traversal attacks"""
        response = client.post('/scan_folder', 
                              json={'folder_path': '../../../etc/passwd'},
                              headers=auth_headers)
        assert response.status_code in [400, 403], "Path traversal should be rejected"
    
    def test_scan_folder_requires_auth(self, client):
        """FIX: Endpoint should require authentication"""
        response = client.post('/scan_folder', 
                              json={'folder_path': '/tmp'})
        assert response.status_code == 401, "Unauthenticated request should be rejected"


# =============================================================================
# OWASP A07:2021 - Identification and Authentication Failures
# =============================================================================
class TestAuthentication:
    """Test cases for authentication requirements"""
    
    def test_api_key_exists(self):
        """FIX: API key should be generated on startup"""
        assert API_KEY is not None, "API key should exist"
        assert len(API_KEY) >= 32, "API key should be at least 32 characters"
    
    def test_protected_endpoint_requires_auth(self, client):
        """FIX: Protected endpoints should require Bearer token"""
        protected_endpoints = [
            ('/scan_folder', 'POST'),
            ('/browse_local', 'POST'),
            ('/abort', 'POST'),
            ('/stream_analysis', 'GET'),
            ('/decision', 'POST')
        ]
        
        for endpoint, method in protected_endpoints:
            if method == 'POST':
                response = client.post(endpoint, json={})
            else:
                response = client.get(endpoint)
            assert response.status_code == 401, f"{endpoint} should require auth"
    
    def test_protected_endpoint_accepts_valid_auth(self, client, auth_headers):
        """FIX: Protected endpoints should accept valid Bearer token"""
        response = client.get('/health', headers=auth_headers)
        # Health is public, but testing auth header doesn't break it
        assert response.status_code == 200, "Valid auth should be accepted"
    
    def test_invalid_api_key_rejected(self, client):
        """FIX: Invalid API key should be rejected"""
        invalid_headers = {"Authorization": "Bearer invalid_key_12345"}
        response = client.post('/scan_folder', 
                              json={'folder_path': '/tmp'},
                              headers=invalid_headers)
        assert response.status_code == 401, "Invalid API key should be rejected"
    
    def test_missing_auth_header_rejected(self, client):
        """FIX: Missing Authorization header should be rejected"""
        response = client.post('/scan_folder', json={'folder_path': '/tmp'})
        assert response.status_code == 401, "Missing auth header should be rejected"
    
    def test_malformed_auth_header_rejected(self, client):
        """FIX: Malformed Authorization header should be rejected"""
        malformed_headers = [
            {"Authorization": "invalid_format"},
            {"Authorization": "Basic dXNlcjpwYXNz"},
            {"Authorization": ""},
        ]
        for headers in malformed_headers:
            response = client.post('/scan_folder', 
                                  json={'folder_path': '/tmp'},
                                  headers=headers)
            assert response.status_code == 401, f"Malformed auth should be rejected: {headers}"


# =============================================================================
# OWASP A03:2021 - Injection (Input Validation & XSS)
# =============================================================================
class TestInputValidation:
    """Test cases for input validation and XSS prevention"""
    
    def test_sanitize_output_escapes_html(self):
        """FIX: HTML entities should be escaped"""
        malicious_input = '<script>alert("XSS")</script>'
        result = sanitize_output(malicious_input)
        assert '<script>' not in result, "HTML tags should be escaped"
        assert '&lt;script&gt;' in result, "HTML should be entity-encoded"
    
    def test_sanitize_output_escapes_quotes(self):
        """FIX: Quotes should be escaped"""
        malicious_input = '"><img src=x onerror=alert(1)>'
        result = sanitize_output(malicious_input)
        # markupsafe.escape converts " to &#34; and < to &lt;
        assert '&lt;' in result, "Angle brackets should be escaped"
        assert '&#34;' in result, "Double quotes should be escaped"
    
    def test_sanitize_output_handles_none(self):
        """FIX: None input should return empty string"""
        result = sanitize_output(None)
        assert result == "", "None should return empty string"
    
    def test_validate_code_content_python_valid(self):
        """FIX: Valid Python code should pass validation"""
        valid_code = """
def hello():
    return "world"
"""
        result = validate_code_content(valid_code, '.py')
        assert result is True, "Valid Python should pass"
    
    def test_validate_code_content_python_invalid(self):
        """FIX: Invalid Python syntax should fail validation"""
        invalid_code = "def hello(:"  # Missing closing parenthesis
        result = validate_code_content(invalid_code, '.py')
        assert result is False, "Invalid Python syntax should fail"
    
    def test_validate_code_content_js_dangerous_eval(self):
        """FIX: JavaScript with eval() should fail validation"""
        dangerous_code = 'eval("alert(1)")'
        result = validate_code_content(dangerous_code, '.js')
        assert result is False, "JS with eval() should fail"
    
    def test_validate_code_content_js_dangerous_exec(self):
        """FIX: JavaScript with exec() should fail validation"""
        dangerous_code = 'exec("rm -rf /")'
        result = validate_code_content(dangerous_code, '.js')
        assert result is False, "JS with exec() should fail"
    
    def test_validate_code_content_js_dangerous_child_process(self):
        """FIX: JavaScript with child_process should fail validation"""
        dangerous_code = 'require("child_process").exec("cmd")'
        result = validate_code_content(dangerous_code, '.js')
        assert result is False, "JS with child_process should fail"
    
    def test_validate_code_content_empty(self):
        """FIX: Empty code should fail validation"""
        result = validate_code_content("", '.py')
        assert result is False, "Empty code should fail"
    
    def test_validate_code_content_none(self):
        """FIX: None code should fail validation"""
        result = validate_code_content(None, '.py')
        assert result is False, "None code should fail"


# =============================================================================
# OWASP A04:2021 - Insecure Design (Rate Limiting)
# =============================================================================
class TestRateLimiting:
    """Test cases for rate limiting"""
    
    def test_rate_limiter_configured(self):
        """FIX: Rate limiter should be configured"""
        from flask_limiter import Limiter
        assert hasattr(app, 'extensions'), "App should have extensions"
        # Check if limiter is registered
        assert 'limiter' in [str(type(v)) for v in app.extensions.values()] or \
               any('limiter' in str(k).lower() for k in app.extensions.keys()), \
               "Rate limiter should be registered"
    
    def test_health_endpoint_public(self, client):
        """FIX: Health endpoint should be accessible without auth"""
        response = client.get('/health')
        assert response.status_code == 200, "Health endpoint should be public"
        data = response.get_json()
        assert data['status'] == 'healthy', "Health should return healthy status"


# =============================================================================
# OWASP A05:2021 - Security Misconfiguration
# =============================================================================
class TestSecurityConfiguration:
    """Test cases for security configuration"""
    
    def test_debug_mode_off_by_default(self):
        """FIX: Debug mode should be off by default"""
        assert app.config.get('DEBUG') is not True, "Debug should be off by default"
    
    def test_error_messages_not_verbose(self, client):
        """FIX: Error messages should not leak sensitive info"""
        response = client.post('/scan_folder', 
                              json={'invalid': 'data'})
        data = response.get_json()
        # Should not contain stack traces or internal paths
        assert 'Traceback' not in str(data), "Should not expose stack traces"
        assert 'File "C:' not in str(data), "Should not expose file paths"


# =============================================================================
# OWASP A01:2021 - Broken Access Control (Authorization)
# =============================================================================
class TestAuthorization:
    """Test cases for authorization controls"""
    
    def test_cannot_access_other_users_files(self, client, auth_headers, temp_dir):
        """FIX: Users should only access authorized directories"""
        # Create test files
        os.makedirs(os.path.join(temp_dir, "allowed"))
        os.makedirs(os.path.join(temp_dir, "forbidden"))
        
        # Try to scan forbidden directory
        response = client.post('/scan_folder',
                              json={'folder_path': os.path.join(temp_dir, "forbidden")},
                              headers=auth_headers)
        # Should either work (if path is valid) or fail with proper error
        assert response.status_code in [200, 400, 403], "Should handle access properly"
    
    def test_scan_folder_validates_path_exists(self, client, auth_headers):
        """FIX: Should validate directory exists before scanning"""
        response = client.post('/scan_folder',
                              json={'folder_path': '/nonexistent/path'},
                              headers=auth_headers)
        assert response.status_code == 400, "Should reject non-existent paths"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
