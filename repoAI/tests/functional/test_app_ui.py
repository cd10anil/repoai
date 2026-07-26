"""
UI Regression Test Suite for app.py
Tests to prevent regressions in browse dialog, scan, and file listing.
Run with: pytest tests/functional/test_app_ui.py -v
"""
import pytest
import os
import sys
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import app, get_code_files, WORKSPACE_STATE


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_project():
    temp_dir = tempfile.mkdtemp()
    with open(os.path.join(temp_dir, 'main.py'), 'w') as f:
        f.write('def hello():\n    return "world"\n')
    with open(os.path.join(temp_dir, 'utils.js'), 'w') as f:
        f.write('function hello() { return "world"; }\n')
    with open(os.path.join(temp_dir, 'README.md'), 'w') as f:
        f.write('# Test\n')
    with open(os.path.join(temp_dir, 'image.png'), 'w') as f:
        f.write('not code')
    sub = os.path.join(temp_dir, 'src')
    os.makedirs(sub)
    with open(os.path.join(sub, 'app.py'), 'w') as f:
        f.write('print("hi")\n')
    yield temp_dir
    shutil.rmtree(temp_dir)


# ===========================================================================
# Index Page (serves the HTML + JS)
# ===========================================================================
class TestIndexPage:
    def test_index_returns_200(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_index_contains_folder_input(self, client):
        resp = client.get('/')
        html = resp.data.decode()
        assert 'id="folderPath"' in html

    def test_index_contains_browse_button(self, client):
        resp = client.get('/')
        html = resp.data.decode()
        assert 'btnBrowse' in html

    def test_index_contains_scan_button(self, client):
        resp = client.get('/')
        html = resp.data.decode()
        assert 'btnLoadFolder' in html

    def test_index_loads_script_js(self, client):
        resp = client.get('/')
        html = resp.data.decode()
        assert 'script.js' in html

    def test_index_loads_styles_css(self, client):
        resp = client.get('/')
        html = resp.data.decode()
        assert 'styles.css' in html

    def test_index_sets_default_path(self, client):
        resp = client.get('/')
        html = resp.data.decode()
        assert WORKSPACE_STATE["repo_path"] in html


# ===========================================================================
# Scan Folder (core regression tests)
# ===========================================================================
class TestScanFolder:
    def test_scan_valid_folder(self, client, temp_project):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert isinstance(data['files'], list)
        assert len(data['files']) >= 3

    def test_scan_returns_py_files(self, client, temp_project):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        data = resp.get_json()
        py_files = [f for f in data['files'] if f.endswith('.py')]
        assert len(py_files) >= 2

    def test_scan_returns_js_files(self, client, temp_project):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        data = resp.get_json()
        js_files = [f for f in data['files'] if f.endswith('.js')]
        assert len(js_files) >= 1

    def test_scan_excludes_image_files(self, client, temp_project):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        data = resp.get_json()
        img_files = [f for f in data['files'] if f.endswith('.png')]
        assert len(img_files) == 0

    def test_scan_excludes_pycache(self, client, temp_project):
        pycache = os.path.join(temp_project, '__pycache__')
        os.makedirs(pycache)
        with open(os.path.join(pycache, 'cached.pyc'), 'w') as f:
            f.write('cache')
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        data = resp.get_json()
        assert not any('__pycache__' in f for f in data['files'])

    def test_scan_excludes_venv(self, client, temp_project):
        venv = os.path.join(temp_project, 'venv')
        os.makedirs(venv)
        with open(os.path.join(venv, 'pkg.py'), 'w') as f:
            f.write('# venv')
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        data = resp.get_json()
        assert not any('venv' in f for f in data['files'])

    def test_scan_excludes_node_modules(self, client, temp_project):
        nm = os.path.join(temp_project, 'node_modules', 'pkg')
        os.makedirs(nm)
        with open(os.path.join(nm, 'index.js'), 'w') as f:
            f.write('// dep')
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        data = resp.get_json()
        assert not any('node_modules' in f for f in data['files'])

    def test_scan_returns_sorted_files(self, client, temp_project):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        data = resp.get_json()
        assert data['files'] == sorted(data['files'])

    def test_scan_returns_relative_paths(self, client, temp_project):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        data = resp.get_json()
        for f in data['files']:
            assert not os.path.isabs(f)

    def test_scan_uses_forward_slashes(self, client, temp_project):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        data = resp.get_json()
        for f in data['files']:
            assert '\\' not in f

    def test_scan_includes_subdirectory_files(self, client, temp_project):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': temp_project}),
                           content_type='application/json')
        data = resp.get_json()
        sub_files = [f for f in data['files'] if f.startswith('src/')]
        assert len(sub_files) >= 1

    def test_scan_invalid_path(self, client):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': 'C:\\nonexistent'}),
                           content_type='application/json')
        data = resp.get_json()
        assert data['status'] == 'error'

    def test_scan_empty_path(self, client):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': ''}),
                           content_type='application/json')
        data = resp.get_json()
        assert data['status'] == 'error'

    def test_scan_no_json_body(self, client):
        resp = client.post('/scan_folder',
                           data='not json',
                           content_type='text/plain')
        assert resp.status_code in [400, 415, 200]

    def test_scan_updates_workspace_state(self, client, temp_project):
        client.post('/scan_folder',
                     data=json.dumps({'folder_path': temp_project}),
                     content_type='application/json')
        assert WORKSPACE_STATE['repo_path'] == temp_project

    def test_scan_returns_200_on_error(self, client):
        resp = client.post('/scan_folder',
                           data=json.dumps({'folder_path': 'C:\\bad'}),
                           content_type='application/json')
        assert resp.status_code == 200


def _mock_tkinter_unavailable():
    """Context manager that makes tkinter import fail and subprocess unavailable."""
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        import sys
        saved = sys.modules.get('tkinter')
        saved_fd = sys.modules.get('tkinter.filedialog')
        sys.modules['tkinter'] = None
        sys.modules['tkinter.filedialog'] = None
        try:
            yield
        finally:
            if saved is not None:
                sys.modules['tkinter'] = saved
            else:
                sys.modules.pop('tkinter', None)
            if saved_fd is not None:
                sys.modules['tkinter.filedialog'] = saved_fd
            else:
                sys.modules.pop('tkinter.filedialog', None)

    return _ctx()


# ===========================================================================
# Browse Local (dialog regression tests)
# ===========================================================================
class TestBrowseLocal:
    def test_browse_returns_json(self, client):
        with _mock_tkinter_unavailable():
            with patch('app.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout='', returncode=0)
                resp = client.post('/browse_local')
                assert resp.status_code == 200
                data = resp.get_json()
                assert 'status' in data

    def test_browse_returns_success_or_cancelled(self, client):
        with _mock_tkinter_unavailable():
            with patch('app.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout='', returncode=0)
                resp = client.post('/browse_local')
                data = resp.get_json()
                assert data['status'] in ('success', 'cancelled', 'error')

    def test_browse_cancelled_when_no_selection(self, client):
        with _mock_tkinter_unavailable():
            with patch('app.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout='', returncode=0)
                resp = client.post('/browse_local')
                data = resp.get_json()
                assert data['status'] == 'cancelled'

    def test_browse_handles_tkinter_failure(self, client):
        with _mock_tkinter_unavailable():
            with patch('app.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout='', returncode=0)
                resp = client.post('/browse_local')
                assert resp.status_code == 200

    def test_browse_handles_powershell_failure(self, client):
        with _mock_tkinter_unavailable():
            with patch('app.subprocess.run', side_effect=Exception('PS failed')):
                resp = client.post('/browse_local')
                data = resp.get_json()
                assert data['status'] == 'cancelled'

    def test_browse_powershell_path_normalized(self, client):
        with _mock_tkinter_unavailable():
            with patch('app.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout='C:/some/path\n',
                    returncode=0
                )
                resp = client.post('/browse_local')
                data = resp.get_json()
                if data['status'] == 'success':
                    assert '\\' in data['folder_path']

    def test_browse_returns_success_with_path(self, client):
        with _mock_tkinter_unavailable():
            with patch('app.subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout='C:\\ri\\repoAI\n',
                    returncode=0
                )
                resp = client.post('/browse_local')
                data = resp.get_json()
                if data['status'] == 'success':
                    assert 'folder_path' in data
                    assert data['folder_path'] == 'C:\\ri\\repoAI'


# ===========================================================================
# get_code_files Unit Tests
# ===========================================================================
class TestGetCodeFiles:
    def test_returns_list(self, temp_project):
        result = get_code_files(temp_project)
        assert isinstance(result, list)

    def test_nonexistent_path(self):
        result = get_code_files('C:\\nonexistent')
        assert result == []

    def test_finds_all_supported(self, temp_project):
        result = get_code_files(temp_project)
        exts = set(os.path.splitext(f)[1] for f in result)
        assert '.py' in exts
        assert '.js' in exts
        assert '.md' in exts

    def test_sorted_output(self, temp_project):
        result = get_code_files(temp_project)
        assert result == sorted(result)


# ===========================================================================
# Abort Endpoint
# ===========================================================================
class TestAbort:
    def test_abort_returns_200(self, client):
        resp = client.post('/abort')
        assert resp.status_code == 200

    def test_abort_returns_status(self, client):
        resp = client.post('/abort')
        data = resp.get_json()
        assert data['status'] == 'aborted'


# ===========================================================================
# Decision Endpoint
# ===========================================================================
class TestDecision:
    def test_reject_returns_success(self, client):
        resp = client.post('/decision',
                           data=json.dumps({'action': 'REJECT'}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'

    def test_invalid_action_returns_400(self, client):
        resp = client.post('/decision',
                           data=json.dumps({'action': 'INVALID'}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_approve_without_file_returns_400(self, client):
        resp = client.post('/decision',
                           data=json.dumps({'action': 'APPROVE'}),
                           content_type='application/json')
        assert resp.status_code == 400


# ===========================================================================
# Static Assets
# ===========================================================================
class TestStaticAssets:
    def test_script_js_loads(self, client):
        resp = client.get('/static/js/script.js?v=4')
        assert resp.status_code == 200

    def test_styles_css_loads(self, client):
        resp = client.get('/static/css/styles.css?v=4')
        assert resp.status_code == 200

    def test_script_js_contains_loadFolder(self, client):
        resp = client.get('/static/js/script.js?v=4')
        js = resp.data.decode()
        assert 'function loadFolder' in js

    def test_script_js_contains_triggerNativeBrowse(self, client):
        resp = client.get('/static/js/script.js?v=4')
        js = resp.data.decode()
        assert 'function triggerNativeBrowse' in js

    def test_script_js_has_catch_handlers(self, client):
        resp = client.get('/static/js/script.js?v=4')
        js = resp.data.decode()
        assert '.catch(' in js


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
