// --- DOM ELEMENTS ---
const terminal = document.getElementById('terminal');
const diffBox = document.getElementById('diffBox');
const controlPanel = document.getElementById('controlPanel');
const statusBadge = document.getElementById('status-badge');
const startBtn = document.getElementById('startBtn');
const abortBtn = document.getElementById('abortBtn');
const fileList = document.getElementById('fileList');
const folderPath = document.getElementById('folderPath');
const btnLoadFolder = document.getElementById('btnLoadFolder');
const activeFileDisplay = document.getElementById('activeFileDisplay');
const analysisMode = document.getElementById('analysisMode');

let currentSelectedFile = "";
let activeEventSource = null;
let loadingInterval = null;
let isPipelineRunning = false;

const loadingStatuses = [
    "Parsing Abstract Syntax Tree (AST)",
    "Analyzing variable scope and lifetime",
    "Mapping cross-module dependencies",
    "Evaluating Technical Debt Index",
    "Waking up local LLM engine",
    "Allocating VRAM for context window"
];

// --- INITIALIZATION & EVENT LISTENERS ---
window.onload = () => { if(folderPath.value) loadFolder(); };

window.addEventListener("beforeunload", function (e) {
    if (isPipelineRunning) {
        e.preventDefault();
        e.returnValue = "An AI analysis is currently running. If you leave, the stream will be lost.";
    }
});

folderPath.addEventListener("keypress", function(event) {
    if (event.key === "Enter") {
        event.preventDefault(); 
        loadFolder();
    }
});

// --- NATIVE FOLDER BROWSER ---
function triggerNativeBrowse() {
    const btnBrowse = document.getElementById('btnBrowse');
    const originalText = btnBrowse.innerText;
    btnBrowse.innerText = "Opening...";
    btnBrowse.disabled = true;

    fetch('/browse_local', { method: 'POST' })
    .then(res => res.json())
    .then(data => {
        btnBrowse.innerText = originalText;
        btnBrowse.disabled = false;
        
        if (data.status === "success" && data.folder_path) {
            folderPath.value = data.folder_path; 
            loadFolder(); 
        }
    })
    .catch(err => {
        btnBrowse.innerText = originalText;
        btnBrowse.disabled = false;
        console.error("Browse failed:", err);
        alert("Failed to open folder dialog. You can type the path manually.");
    });
}

// --- SIDEBAR RESIZER LOGIC ---
const sidebar = document.getElementById('sidebar');
const resizer = document.getElementById('resizer');
const btnShowSidebar = document.getElementById('btnShowSidebar');
const contentArea = document.querySelector('.content-area');
let isResizing = false;

function toggleSidebar() {
    sidebar.classList.toggle('collapsed');
    if (sidebar.classList.contains('collapsed')) {
        resizer.style.display = 'none';
        btnShowSidebar.style.display = 'block';
    } else {
        resizer.style.display = 'flex';
        btnShowSidebar.style.display = 'none';
    }
}

resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    resizer.classList.add('active');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    contentArea.style.pointerEvents = 'none'; 
    e.preventDefault(); 
});

window.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const newWidth = e.clientX - sidebar.getBoundingClientRect().left;
    if (newWidth >= 150 && newWidth <= 800) {
        sidebar.style.width = newWidth + 'px';
        sidebar.style.flexBasis = newWidth + 'px';
    }
});

window.addEventListener('mouseup', () => {
    if (isResizing) {
        isResizing = false;
        resizer.classList.remove('active');
        document.body.style.cursor = 'default';
        document.body.style.userSelect = 'auto';
        contentArea.style.pointerEvents = 'auto';
    }
});

// --- MAIN APPLICATION LOGIC ---
function loadFolder() {
    if (!folderPath.value || folderPath.value.trim() === "") {
        fileList.innerHTML = '<li style="color: orange;">Please enter a folder path first.</li>';
        return;
    }

    btnLoadFolder.innerText = "Scanning...";
    btnLoadFolder.disabled = true;
    
    fetch('/scan_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folderPath.value })
    })
    .then(res => res.json())
    .then(data => {
        btnLoadFolder.innerText = "Scan Project";
        btnLoadFolder.disabled = false;
        
        if (data.status === "success") {
            fileList.innerHTML = "";
            data.files.forEach(file => {
                const li = document.createElement('li');
                li.className = 'file-item';
                li.innerText = file;
                li.onclick = () => selectFile(file, li);
                fileList.appendChild(li);
            });
        } else {
            fileList.innerHTML = `<li style="color: red;">${data.message}</li>`;
        }
    })
    .catch(err => {
        btnLoadFolder.innerText = "Scan Project";
        btnLoadFolder.disabled = false;
        console.error("Scan failed:", err);
        fileList.innerHTML = `<li style="color: red;">Scan failed: ${err.message}. Is the server running?</li>`;
    });
}

function selectFile(file, liElement) {
    if (isPipelineRunning) return;

    document.querySelectorAll('.file-item').forEach(el => el.classList.remove('selected'));
    liElement.classList.add('selected');
    
    currentSelectedFile = file;
    activeFileDisplay.innerText = "Analyzing: " + file;
    startBtn.disabled = false;
    
    terminal.style.display = 'block';
    diffBox.style.display = 'none';
    controlPanel.style.display = 'none';
    
    terminal.innerText = `Selected ${file}. Ready to execute agents.`;
    statusBadge.innerText = "Ready";
}

function writeTerminal(text, overwriteLine = false) {
    const isAtBottom = terminal.scrollHeight - terminal.clientHeight <= terminal.scrollTop + 50;
    if (overwriteLine) {
        let lines = terminal.innerText.split('\n');
        lines[lines.length - 1] = text;
        terminal.innerText = lines.join('\n');
    } else {
        terminal.innerText += text;
    }
    if (isAtBottom) terminal.scrollTop = terminal.scrollHeight;
}

function abortAnalysis() {
    fetch('/abort', { method: 'POST' }).then(() => {
        if(activeEventSource) {
            activeEventSource.close();
            clearInterval(loadingInterval);
            writeTerminal("\n\n[SYSTEM] Agentic workflow aborted by user.");
            statusBadge.innerText = "Aborted";
            resetUIState();
        }
    }).catch(err => console.error("Abort failed:", err));
}

function resetUIState() {
    isPipelineRunning = false;
    startBtn.style.display = 'block';
    abortBtn.style.display = 'none';
    btnLoadFolder.disabled = false;
    folderPath.disabled = false;
    document.querySelectorAll('.file-item').forEach(el => el.style.pointerEvents = 'auto');
}

function injectGranularTooltips() {
    const allLines = document.querySelectorAll('.d2h-code-line-ct, .d2h-code-line ct');
    
    allLines.forEach(line => {
        const text = line.innerText;
        // Hunts down the # FIX: tag even if it has syntax highlighting spans inside it
        const match = text.match(/#\s*FIX:\s*(.*)/i);
        
        if (match) {
            const reason = match[1].trim();

            const badge = document.createElement('span');
            badge.className = 'ai-badge';
            // Now the badge shows the actual reason directly on the screen!
            badge.innerText = '💡 ' + reason; 
            badge.title = reason; 

            // Wipe out the messy syntax-highlighted HTML and replace it with the clean badge
            line.innerHTML = '';
            line.appendChild(badge);
        }
    });
}

function startAnalysis(isTweak = false, feedback = "") {
    if (!currentSelectedFile) return;

    isPipelineRunning = true;
    startBtn.style.display = 'none';
    abortBtn.style.display = 'block';
    diffBox.style.display = 'none';
    controlPanel.style.display = 'none';
    
    btnLoadFolder.disabled = true;
    folderPath.disabled = true;
    document.querySelectorAll('.file-item').forEach(el => el.style.pointerEvents = 'none');
    
    statusBadge.innerText = isTweak ? "Refining Code..." : "Running Agents...";
    terminal.style.display = 'block';
    terminal.innerText = `[Agent 1: Discovery] Analyzing ${currentSelectedFile}...\n`;
    
    let statusIndex = 0;
    let firstTokenReceived = false;
    let ticks = 0;
    const spinnerChars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

    loadingInterval = setInterval(() => {
        if (firstTokenReceived) return;

        if (statusIndex < loadingStatuses.length) {
            let dotsCount = Math.floor(ticks / 5) % 4;
            writeTerminal(` -> ${loadingStatuses[statusIndex]}${".".repeat(dotsCount)}`, true);
            
            if (ticks > 0 && ticks % 20 === 0) {
                statusIndex++;
                writeTerminal("\n"); 
            }
        } else {
            const char = spinnerChars[ticks % spinnerChars.length];
            writeTerminal(` -> Awaiting first token from LLM... ${char}`, true);
        }
        ticks++;
    }, 100);

    const mode = analysisMode.value;
    let url = `/stream_analysis?file=${encodeURIComponent(currentSelectedFile)}&mode=${mode}`;
    if (isTweak) url += `&feedback=${encodeURIComponent(feedback)}`;
    
    activeEventSource = new EventSource(url);

    // Track when the LLM starts writing code so we can hide it
    let tokenBuffer = "";
    let foundCodeBlock = false;

    activeEventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);

        if (data.type === 'abort') {
            activeEventSource.close();
            clearInterval(loadingInterval);
            return; 
        }
        else if (data.type === 'token') {
            if (!firstTokenReceived) {
                firstTokenReceived = true;
                clearInterval(loadingInterval);
                writeTerminal("\n\n -> Streaming response live from LLM...\n\n");
            }

            // The Smart Filter: Only print text if we haven't hit the code block yet
            if (!foundCodeBlock) {
                tokenBuffer += data.content;
                writeTerminal(data.content);

                // If we detect the markdown backticks, stop printing and show a clean message
                if (tokenBuffer.includes('```')) {
                    foundCodeBlock = true;
                    writeTerminal("\n\n[SYSTEM] AI is rewriting the file to inject fixes. Please wait...\n(Raw code streaming is hidden to keep the console clean)");
                }
            }
        } 
        else if (data.type === 'diff') {
            activeEventSource.close();
            resetUIState();
            
            terminal.style.display = 'none';
            
            var diffHtml = Diff2Html.html(data.diff_string, {
                drawFileList: false, 
                matching: 'lines',
                outputFormat: 'side-by-side',
                renderNothingWhenEmpty: false
            });
            diffBox.innerHTML = diffHtml;
            
            injectGranularTooltips();
            
            diffBox.style.display = 'block';
            controlPanel.style.display = 'flex';
            statusBadge.innerText = "Awaiting Human Review";
            diffBox.scrollTop = 0;
        }
    };

    activeEventSource.onerror = function() {
        activeEventSource.close();
        clearInterval(loadingInterval);
        resetUIState();
        writeTerminal("\n\n[ERROR] Connection to Agentic Backend lost.");
        statusBadge.innerText = "Error";
    };
}

function submitDecision(action) {
    const feedback = document.getElementById('tweakInput').value;
    if (action === 'MODIFY' && feedback.trim() === "") {
        alert("Please enter a tweak request.");
        return;
    }
    if (action === 'MODIFY') {
        startAnalysis(true, feedback);
        return;
    }
    fetch('/decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    })
    .then(response => response.json())
    .then(data => {
        controlPanel.style.display = 'none';
        
        if (action === 'APPROVE') {
            statusBadge.innerText = "Merged";
            diffBox.style.display = 'none';
            terminal.style.display = 'block';
            
            const backupInfo = data.backup_created ? `\n[Backup] Original code preserved as: ${data.backup_created}` : '';
            writeTerminal(`\n\n[System] Changes Approved. File successfully overwritten.${backupInfo}\nBase Path: ${data.output_dir}`);
        } else {
            statusBadge.innerText = "Rejected";
            diffBox.style.display = 'none';
            terminal.style.display = 'block';
            writeTerminal(`\n\n[System] Fix Rejected. Modifications discarded.`);
        }
    })
    .catch(err => {
        console.error("Decision failed:", err);
        controlPanel.style.display = 'none';
        terminal.style.display = 'block';
        writeTerminal(`\n\n[ERROR] Failed to submit decision: ${err.message}`);
        statusBadge.innerText = "Error";
    });
}