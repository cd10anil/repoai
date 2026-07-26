import os
import json
import difflib
import re
import ast
import secrets
from flask import Flask, render_template, Response, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from typing import Dict
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from markupsafe import escape
import shutil
import threading
from functools import wraps

app = Flask(__name__)

# =====================================================================
# SECURITY: Rate Limiter Configuration
# =====================================================================
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour", "20 per minute"],
    storage_uri="memory://"
)

# =====================================================================
# SECURITY: Authentication Configuration
# =====================================================================
API_KEY = secrets.token_hex(32)
print(f"[SECURITY] API Key generated: {API_KEY[:8]}...{API_KEY[-8:]}")

def require_auth(f):
    """OWASP A07:2021 - Authentication required for sensitive endpoints"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer ') or auth_header[7:] != API_KEY:
            return jsonify({"error": "Unauthorized - Valid API key required"}), 401
        return f(*args, **kwargs)
    return decorated

# =====================================================================
# SECURITY: Path Validation Utilities
# =====================================================================
def is_path_safe(base_dir, target_path):
    """OWASP A01:2021 - Path Traversal Prevention"""
    try:
        base_dir = os.path.realpath(base_dir)
        target_full = os.path.realpath(os.path.join(base_dir, target_path))
        return target_full.startswith(base_dir + os.sep) or target_full == base_dir
    except (ValueError, OSError):
        return False

def validate_folder_path(path):
    """OWASP A03:2021 - Input Validation for folder paths"""
    if not path or not isinstance(path, str):
        return False
    
    # Fix: Check for null bytes
    if '\x00' in path:
        return False
    
    # Fix: Check for dangerous patterns
    dangerous_patterns = [r'\.\.', r'~', r'\$\{', r'%00', r'%2e%2e']
    for pattern in dangerous_patterns:
        if re.search(pattern, path, re.IGNORECASE):
            return False
    
    # Fix: Check path exists and is directory
    return os.path.isdir(path)

# =====================================================================
# SECURITY: Code Validation Utilities
# =====================================================================
def validate_code_content(code, file_extension):
    """OWASP A04:2021 - Validate code before writing to prevent injection"""
    if not code or not isinstance(code, str):
        return False
    
    if file_extension == '.py':
        try:
            ast.parse(code)  # Fix: Syntax check for Python
            return True
        except SyntaxError:
            return False
    elif file_extension in ['.js', '.ts', '.tsx', '.jsx']:
        # Fix: Basic pattern checks for JS/TS
        dangerous_patterns = [
            r'eval\s*\(',
            r'exec\s*\(',
            r'child_process',
            r'shell\s*=',
            r'require\s*\(\s*["\']child_process',
            r'process\.exit'
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return False
    return True

def sanitize_output(text):
    """OWASP A03:2021 - XSS Prevention"""
    if text is None:
        return ""
    return escape(text)

# =====================================================================
# GLOBAL CONFIGURATION
# =====================================================================
TARGET_PROJECT_DIR = os.getenv('TARGET_PROJECT_DIR', r"C:\ri\repoAI\sample_enterprise_project")

# 1 = Force GPU Acceleration (Offload all layers to VRAM)
# 0 = Force CPU Only (Slower, but uses System RAM)
ENABLE_GPU_ACCELERATION = int(os.getenv('ENABLE_GPU_ACCELERATION', '1'))

SUPPORTED_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', 
    '.c', '.cs', '.html', '.css', '.vb', '.json', '.md'
}

# --- INTERNAL STATE TRACKING ---
WORKSPACE_STATE = {
    "repo_path": TARGET_PROJECT_DIR,
    "target_file": "", 
    "current_code": "",
    "proposed_fix": "",
    "iteration_count": 0
}

GLOBAL_ABORT = False

# --- DYNAMIC HARDWARE PROBING ---
llm_kwargs = {
    "model": os.getenv('LLM_MODEL', 'qwen2.5-coder:1.5b'),
    "temperature": 0.1,
}

if ENABLE_GPU_ACCELERATION == 1:
    print("[SYSTEM] Explicit GPU Acceleration ENABLED. Forcing model layers to VRAM.")
    llm_kwargs["num_gpu"] = 99
else:
    print("[SYSTEM] GPU Acceleration DISABLED. Forcing CPU-only execution.")
    llm_kwargs["num_gpu"] = 0

llm_engine = ChatOllama(**llm_kwargs)

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================
def get_code_files(base_path):
    file_list = []
    if not os.path.exists(base_path):
        return file_list

    for root, dirs, filenames in os.walk(base_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '.venv', '__pycache__']]
        for f in filenames:
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                rel_path = os.path.relpath(os.path.join(root, f), base_path)
                file_list.append(rel_path.replace("\\", "/"))
    return sorted(file_list)

# =====================================================================
# ROUTES - PUBLIC (No Auth Required)
# =====================================================================
@app.route('/')
@limiter.limit("30 per minute")
def index():
    return render_template('index.html', default_path=WORKSPACE_STATE["repo_path"])

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

@app.route('/auth/key')
def get_api_key():
    """Get API key for authentication - ONLY for development"""
    return jsonify({"api_key": API_KEY, "warning": "This is for development only"})

# =====================================================================
# ROUTES - PROTECTED (Auth Required)
# =====================================================================
@app.route('/browse_local', methods=['POST'])
@require_auth
@limiter.limit("5 per minute")
def browse_local():
    """Uses a dedicated thread to safely open the Windows folder dialog without freezing Flask"""
    result = {"path": ""}

    def open_dialog():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            result["path"] = filedialog.askdirectory(title="Select Enterprise Project Folder")
            root.destroy()
        except Exception as e:
            print(f"[SYSTEM ERROR] Tkinter dialog failed: {e}")

    dialog_thread = threading.Thread(target=open_dialog)
    dialog_thread.start()
    dialog_thread.join()

    if result["path"]:
        folder_path = result["path"].replace("/", "\\")
        return jsonify({"status": "success", "folder_path": folder_path})
        
    return jsonify({"status": "cancelled"})

@app.route('/scan_folder', methods=['POST'])
@require_auth
@limiter.limit("10 per minute")
def scan_folder():
    data = request.json
    
    # Fix: Input validation
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    folder_path = data.get('folder_path', '')
    
    # Fix: Validate folder path before use
    if not validate_folder_path(folder_path):
        return jsonify({"status": "error", "message": "Invalid directory path"}), 400
    
    WORKSPACE_STATE["repo_path"] = folder_path
    files = get_code_files(folder_path)
    return jsonify({"status": "success", "files": files})

@app.route('/abort', methods=['POST'])
@require_auth
def abort_analysis():
    global GLOBAL_ABORT
    GLOBAL_ABORT = True
    return jsonify({"status": "aborted"})

@app.route('/stream_analysis')
@require_auth
@limiter.limit("3 per minute")
def stream_analysis():
    global GLOBAL_ABORT
    GLOBAL_ABORT = False 
    
    target_file = request.args.get('file', '')
    feedback = request.args.get('feedback', '')
    mode = request.args.get('mode', 'both')
    
    # Fix: Validate mode parameter
    valid_modes = ['both', 'refactor', 'security']
    if mode not in valid_modes:
        mode = 'both'
    
    # Fix: Path traversal prevention
    if not is_path_safe(WORKSPACE_STATE["repo_path"], target_file):
        return jsonify({"error": "Path traversal detected"}), 403
    
    full_path = os.path.join(WORKSPACE_STATE["repo_path"], target_file)
    
    # Fix: Validate file exists and is readable
    if not os.path.isfile(full_path):
        return jsonify({"error": "File not found"}), 404
    
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            WORKSPACE_STATE["current_code"] = f.read()
    except (IOError, UnicodeDecodeError) as e:
        return jsonify({"error": f"Cannot read file: {str(e)}"}), 500
    
    WORKSPACE_STATE["target_file"] = target_file
    
    def generate():
        WORKSPACE_STATE["iteration_count"] += 1
        
        mode_instructions = {
            "both": "Perform both code refactoring and security vulnerability remediation.",
            "refactor": "Focus ONLY on code refactoring, optimization, and technical debt. Do not modify security logic.",
            "security": "Focus ONLY on identifying and patching security vulnerabilities (e.g., OWASP, injections, weak crypto)."
        }
        
        system_prompt = f"""
        You are an expert enterprise developer. {mode_instructions.get(mode)}
        
        CRITICAL RULES:
        1. Output ONLY the raw code inside standard markdown blocks. No introductory text.
        2. DO NOT ACT LIKE AN AUDITOR. You must ACTUALLY REWRITE the code to fix the vulnerabilities or tech debt. Do not just annotate broken code.
        3. For every block of code you actively change, YOU MUST add an inline comment directly above it exactly like this:
           `# FIX: [Provide OWASP ID, CVE, or specific Refactoring Reason]`
        """
        
        user_prompt = f"Target File: {target_file}\n\nRefactor the following code:\n\n{WORKSPACE_STATE['current_code']}"
        if feedback:
            # Fix: Sanitize feedback input
            sanitized_feedback = sanitize_output(feedback)
            user_prompt += f"\n\nUser request for changes:\n{sanitized_feedback}\nApply this exact instruction."

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
                
        content = ""
        for chunk in llm_engine.stream(messages):
            if GLOBAL_ABORT:
                yield f"data: {json.dumps({'type': 'abort'})}\n\n"
                break
                
            content += chunk.content
            yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"
        
        if GLOBAL_ABORT:
            return

        if "```" in content:
            code_block = content.split("```")[1]
            if "\n" in code_block:
                code_block = "\n".join(code_block.split("\n")[1:])
        else:
            code_block = content
            
        WORKSPACE_STATE["proposed_fix"] = code_block.strip()
        
        raw_diff_list = difflib.unified_diff(
            WORKSPACE_STATE["current_code"].splitlines(),
            WORKSPACE_STATE["proposed_fix"].splitlines(),
            fromfile=f"Original: {target_file}",
            tofile=f"AI Proposed: {target_file}",
            lineterm=''
        )
        
        diff_string = '\n'.join(raw_diff_list)
        
        # Fix: Sanitize diff output for XSS prevention
        safe_diff = sanitize_output(diff_string)
        yield f"data: {json.dumps({'type': 'diff', 'diff_string': safe_diff})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/decision', methods=['POST'])
@require_auth
@limiter.limit("10 per minute")
def handle_decision():
    data = request.json
    
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    action = data.get('action')
    
    if action == 'APPROVE':
        file_rel_path = WORKSPACE_STATE["target_file"]
        if not file_rel_path:
            return jsonify({"status": "error", "message": "No active file selected"}), 400
        
        # Fix: Path traversal prevention
        if not is_path_safe(WORKSPACE_STATE["repo_path"], file_rel_path):
            return jsonify({"error": "Path traversal detected"}), 403
            
        full_path = os.path.join(WORKSPACE_STATE["repo_path"], file_rel_path)
        
        # Fix: Validate code content before writing
        file_ext = os.path.splitext(file_rel_path)[1].lower()
        if not validate_code_content(WORKSPACE_STATE["proposed_fix"], file_ext):
            return jsonify({"error": "Code validation failed - potentially unsafe content detected"}), 400
        
        if os.path.exists(full_path):
            counter = 1
            backup_path = f"{full_path}.bak{counter}"
            while os.path.exists(backup_path):
                counter += 1
                backup_path = f"{full_path}.bak{counter}"
            
            shutil.copy2(full_path, backup_path)
            print(f"[SYSTEM] Created secure backup at: {backup_path}")
        
        # Fix: Write with error handling
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(WORKSPACE_STATE["proposed_fix"])
        except IOError as e:
            return jsonify({"error": f"Failed to write file: {str(e)}"}), 500
            
        print(f"[SYSTEM] Successfully merged improvements into: {full_path}")
        
        return jsonify({
            "status": "success", 
            "message": "Merged successfully", 
            "output_dir": WORKSPACE_STATE["repo_path"],
            "backup_created": os.path.basename(backup_path)
        })
        
    elif action == 'REJECT':
        WORKSPACE_STATE["proposed_fix"] = ""
        return jsonify({"status": "success", "message": "Changes rejected"})
        
    return jsonify({"status": "error", "message": "Invalid action"}), 400

# =====================================================================
# MAIN ENTRY POINT
# =====================================================================
if __name__ == '__main__':
    # Fix: Use environment variables for configuration
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))
    
    if debug_mode:
        print("[WARNING] Debug mode is ON - not for production!")
    
    print("\n" + "="*60)
    print(" SECURE AGENTIC AI SERVER RUNNING")
    print(f" URL: http://{host}:{port}")
    print(f" API Key: {API_KEY[:8]}...{API_KEY[-8:]}")
    print("="*60 + "\n")
    
    app.run(debug=debug_mode, host=host, port=port)
