import os
import json
import difflib
from flask import Flask, render_template, Response, request, jsonify
from typing import Dict
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
import shutil
import threading

app = Flask(__name__)

# =====================================================================
# GLOBAL CONFIGURATION
# =====================================================================
TARGET_PROJECT_DIR = r"C:\ri\repoAI\sample_enterprise_project"

# 1 = Force GPU Acceleration (Offload all layers to VRAM)
# 0 = Force CPU Only (Slower, but uses System RAM)
ENABLE_GPU_ACCELERATION = 1 

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
    "model": "qwen2.5-coder:1.5b",
    "temperature": 0.1,
}

if ENABLE_GPU_ACCELERATION == 1:
    print("[SYSTEM] Explicit GPU Acceleration ENABLED. Forcing model layers to VRAM.")
    llm_kwargs["num_gpu"] = 99  # -1 tells the engine to push ALL available layers to the GPU, # Changed from -1 to 99 to strictly enforce all layers
else:
    print("[SYSTEM] GPU Acceleration DISABLED. Forcing CPU-only execution.")
    llm_kwargs["num_gpu"] = 0   # 0 explicitly blocks the GPU from being used

llm_engine = ChatOllama(**llm_kwargs)

# ... [Inside get_code_files function] ...
def get_code_files(base_path):
    file_list = []
    if not os.path.exists(base_path):
        return file_list

    for root, dirs, filenames in os.walk(base_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', 'venv', '.venv', '__pycache__']]
        for f in filenames:
            # Use the global configuration!
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                rel_path = os.path.relpath(os.path.join(root, f), base_path)
                file_list.append(rel_path.replace("\\", "/"))
    return sorted(file_list)

@app.route('/')
def index():
    return render_template('index.html', default_path=WORKSPACE_STATE["repo_path"])

@app.route('/browse_local', methods=['POST'])
def browse_local():
    """Uses a dedicated thread to safely open the Windows folder dialog without freezing Flask"""
    result = {"path": ""}

    def open_dialog():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True) # Force to front
            result["path"] = filedialog.askdirectory(title="Select Enterprise Project Folder")
            root.destroy()
        except Exception as e:
            print(f"[SYSTEM ERROR] Tkinter dialog failed: {e}")

    # Run the UI dialog in a safe, isolated thread
    dialog_thread = threading.Thread(target=open_dialog)
    dialog_thread.start()
    dialog_thread.join() # Wait for the user to pick a folder

    if result["path"]:
        folder_path = result["path"].replace("/", "\\")
        return jsonify({"status": "success", "folder_path": folder_path})
        
    return jsonify({"status": "cancelled"})

@app.route('/scan_folder', methods=['POST'])
def scan_folder():
    data = request.json
    folder_path = data.get('folder_path', '')
    if os.path.isdir(folder_path):
        WORKSPACE_STATE["repo_path"] = folder_path
        files = get_code_files(folder_path)
        return jsonify({"status": "success", "files": files})
    return jsonify({"status": "error", "message": "Invalid directory path."})

@app.route('/abort', methods=['POST'])
def abort_analysis():
    global GLOBAL_ABORT
    GLOBAL_ABORT = True
    return jsonify({"status": "aborted"})

@app.route('/stream_analysis')
def stream_analysis():
    global GLOBAL_ABORT
    GLOBAL_ABORT = False 
    
    target_file = request.args.get('file', '')
    feedback = request.args.get('feedback', '')
    mode = request.args.get('mode', 'both')
    
    WORKSPACE_STATE["target_file"] = target_file
    full_path = os.path.join(WORKSPACE_STATE["repo_path"], target_file)
    with open(full_path, "r", encoding="utf-8") as f:
        WORKSPACE_STATE["current_code"] = f.read()
    
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
        3. For every block of code you actively change, you MUST add an inline comment directly above it exactly like this:
           `# FIX: [Provide OWASP ID, CVE, or specific Refactoring Reason]`
        """
        
        user_prompt = f"Target File: {target_file}\n\nRefactor the following code:\n\n{WORKSPACE_STATE['current_code']}"
        if feedback:
            user_prompt += f"\n\nUser request for changes:\n{feedback}\nApply this exact instruction."

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
        yield f"data: {json.dumps({'type': 'diff', 'diff_string': diff_string})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/decision', methods=['POST'])
def handle_decision():
    data = request.json
    action = data.get('action')
    
    if action == 'APPROVE':
        file_rel_path = WORKSPACE_STATE["target_file"]
        if not file_rel_path:
            return jsonify({"status": "error", "message": "No active file selected"}), 400
            
        full_path = os.path.join(WORKSPACE_STATE["repo_path"], file_rel_path)
        
        if os.path.exists(full_path):
            # 1. Generate incremental backup name (.bak1, .bak2, etc.)
            counter = 1
            backup_path = f"{full_path}.bak{counter}"
            while os.path.exists(backup_path):
                counter += 1
                backup_path = f"{full_path}.bak{counter}"
            
            # 2. Copy the original file to the backup location
            shutil.copy2(full_path, backup_path)
            print(f"[SYSTEM] Created secure backup at: {backup_path}")
        
        # 3. Write the AI proposed code back to the original file
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(WORKSPACE_STATE["proposed_fix"])
            
        print(f"[SYSTEM] Successfully merged improvements into: {full_path}")
        
        return jsonify({
            "status": "success", 
            "message": "Merged successfully", 
            "output_dir": WORKSPACE_STATE["repo_path"],
            "backup_created": os.path.basename(backup_path)
        })
        
    elif action == 'REJECT':
        # Clear out proposed state
        WORKSPACE_STATE["proposed_fix"] = ""
        return jsonify({"status": "success", "message": "Changes rejected"})
        
    return jsonify({"status": "error", "message": "Invalid action"}), 400

if __name__ == '__main__':
    print("\n==================================================================")
    print(" 🚀 AGENTIC AI SERVER RUNNING")
    print(" 👉 Open your browser and go to: http://127.0.0.1:5000")
    print("==================================================================\n")
    app.run(debug=True, port=5000)