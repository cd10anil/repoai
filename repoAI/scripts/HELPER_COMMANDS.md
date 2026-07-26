# Helper Commands Reference

**Purpose:** All commands used during development sessions with reasoning.  
**Created:** 2026-07-26  
**Keep Updated:** Yes — append new commands as they are used.

---

## 1. OpenCode Session Recovery (2026-07-26)

The user wanted to recover their exact typed messages from previous sessions.  
OpenCode doesn't expose chat history in the CLI — messages are stored in a SQLite database.

### Finding the database location

```bash
# Check OpenCode config directory for stored data
Get-ChildItem "$env:USERPROFILE\.config\opencode" -Recurse -File -ErrorAction SilentlyContinue | Select-Object FullName, Length, LastWriteTime | Sort-Object LastWriteTime -Descending | Select-Object -First 20
```
**Reason:** OpenCode stores config in `~/.config/opencode/` — looking for any chat logs or session files.

```bash
# Check OpenCode local share directory for persistent data
Get-ChildItem "$env:USERPROFILE\.local\share\opencode" -Recurse -File -ErrorAction SilentlyContinue | Select-Object FullName, Length, LastWriteTime | Sort-Object LastWriteTime -Descending | Select-Object -First 20
```
**Reason:** Found `opencode.db` — SQLite database with all session data including messages.

### Inspecting the database

```bash
# List all tables in the OpenCode database
python -c "import sqlite3; conn = sqlite3.connect(r'C:\Users\hp\.local\share\opencode\opencode.db'); cursor = conn.cursor(); cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"); print('Tables:', [r[0] for r in cursor.fetchall()])"
```
**Reason:** Needed to understand database schema before extracting messages.

```bash
# Full database inspection script (created as _check_db.py)
Set-Location "C:\ri\repoAI"; python _check_db.py
```
**Reason:** One-liner was getting too complex — created a script to inspect all tables, row counts, columns, and sample data.

### Extracting user messages

```bash
# Run extraction script (created as _extract_messages.py)
Set-Location "C:\ri\repoAI"; python _extract_messages.py
```
**Reason:** Joined `message` and `part` tables to get all user-typed text, filtered by `role='user'`, ordered by timestamp. Found 39 messages across 3 sessions.

---

## 2. Security Audit (2026-07-26)

### Running security tests

```bash
# Run all 34 OWASP security tests
Set-Location "C:\ri\repoAI"; python -m pytest tests/security/ -v
```
**Reason:** Validates all 7 OWASP fixes are working correctly.

```bash
# Run all 28 functional tests
Set-Location "C:\ri\repoAI"; python -m pytest tests/functional/test_app_functionality.py -v
```
**Reason:** Tests app_secure.py endpoints (login, upload, scan, rate limiting).

```bash
# Run all 44 UI regression tests
Set-Location "C:\ri\repoAI"; python -m pytest tests/functional/test_app_ui.py -v
```
**Reason:** Tests original app.py (browse dialog, scan button, file listing) to prevent regressions.

```bash
# Run full test suite (106 tests total)
Set-Location "C:\ri\repoAI"; python -m pytest tests/ -v
```
**Reason:** Quick verification that everything passes before committing.

---

## 3. Flask App Management

### Starting the app

```bash
# Start Flask app in background (used for UI testing)
Start-Process python -ArgumentList "app.py" -WorkingDirectory "C:\ri\repoAI" -WindowStyle Hidden
```
**Reason:** Needed app running to test browse/scan buttons. Used `-WindowStyle Hidden` to avoid blocking terminal.

```bash
# Stop Flask app (kill by port)
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*app.py*" } | Stop-Process -Force
```
**Reason:** Clean shutdown before restarting with changes.

### Testing endpoints

```bash
# Test login endpoint
curl -X POST http://127.0.0.1:5000/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"password\"}"
```
**Reason:** Verify authentication works with valid credentials.

```bash
# Test rate limiting
curl -X POST http://127.0.0.1:5000/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"wrong\"}" (repeat 6 times)
```
**Reason:** Confirm rate limiter blocks after 5 failed attempts.

```bash
# Test file upload validation
curl -X POST http://127.0.0.1:5000/upload -F "file=@test.py" -H "Authorization: Bearer <token>"
```
**Reason:** Verify malicious code detection and file type restrictions.

---

## 4. Git Operations

### Status and history

```bash
# Check current branch and status
Set-Location "C:\ri\repoAI"; git status
```
**Reason:** See what files are modified/staged before committing.

```bash
# View recent commit history
Set-Location "C:\ri\repoAI"; git log --oneline -10
```
**Reason:** Confirm commit messages and see what was recently changed.

### Committing and pushing

```bash
# Stage specific files
Set-Location "C:\ri\repoAI"; git add USER_REQUEST_LOG.md
```
**Reason:** Stage only the files intended for commit, not entire repo.

```bash
# Commit with descriptive message
Set-Location "C:\ri\repoAI"; git commit -m "Add DB location note and entry #40 to USER_REQUEST_LOG.md"
```
**Reason:** Clear commit message following project conventions.

```bash
# Push to remote
Set-Location "C:\ri\repoAI"; git push
```
**Reason:** Upload commits to GitHub.

### Handling push rejections

```bash
# Amend last commit to fix secret detection
Set-Location "C:\ri\repoAI"; git commit --amend -m "Redact DeepSeek API key in USER_REQUEST_LOG.md"
```
**Reason:** GitHub blocked push due to API key in commit — redacted and amended.

```bash
# Squash commits to remove secret from history
Set-Location "C:\ri\repoAI"; git reset --soft HEAD~2; if ($?) { git commit -m "Update USER_REQUEST_LOG.md with all 39 exact user messages (API key redacted)" }
```
**Reason:** Amending didn't remove secret from earlier commit — squashed both commits into one clean commit.

---

## 5. PowerShell Helpers

### Encoding issues

```bash
# Check if file has emoji characters (Windows cp1252 crash)
python -c "with open('app.py', encoding='utf-8') as f: print('OK')"
```
**Reason:** Windows terminal crashed with `UnicodeEncodeError` when Flask printed emoji in output.

### Process management

```bash
# Find running Python processes
Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, CommandLine
```
**Reason:** Identify which Flask instances are running to avoid port conflicts.

### File operations

```bash
# Remove temporary files
Remove-Item _check_db.py, _extract_messages.py -ErrorAction SilentlyContinue
```
**Reason:** Clean up temp scripts after moving to `scripts/` folder.

---

## 6. Pytest Configuration

```ini
# pytest.ini settings
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```
**Reason:** Tells pytest where to find tests and what naming patterns to use.

---

## 7. GitHub Actions CI/CD

```yaml
# .github/workflows/security-tests.yml
# Runs: python -m pytest tests/ -v
# Triggers: push to main, pull requests
```
**Reason:** Automated testing on every commit — catches regressions before merge.

---

## Quick Reference

| Task | Command |
|------|---------|
| Run all tests | `python -m pytest tests/ -v` |
| Run security tests only | `python -m pytest tests/security/ -v` |
| Run UI tests only | `python -m pytest tests/functional/test_app_ui.py -v` |
| Start Flask app | `python app.py` |
| Check DB structure | `python scripts/check_db.py` |
| Extract user messages | `python scripts/extract_messages.py` |
| Git status | `git status` |
| Git push | `git push` |

---

**Last Updated:** 2026-07-26  
**Total Commands Documented:** 25  
**Next Review:** After next user request
