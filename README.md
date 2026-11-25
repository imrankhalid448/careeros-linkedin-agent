# Personal Career & LinkedIn AI Agent (100% Free & Local)

A modular, local-first personal AI agent built with **React + FastAPI + SQLite** and powered by **Ollama** (100% free local AI) by default.  
Designed with a **pluggable Platform Connector architecture** (`backend/app/connectors/`) so LinkedIn works first and additional platforms (GitHub, X/Twitter, Gmail, Portfolio) can be added cleanly later.

---

## 1. Quick Start on Windows

### A. Install Free Local AI (Ollama)
1. Download/open Ollama on Windows and pull a model:
   ```powershell
   ollama pull qwen2.5:7b
   ```
2. Make sure Ollama is running (`ollama serve` or the Windows tray app).

### B. Backend Setup (Python — Conda `env310tfgpu`)
```powershell
cd backend
conda activate env310tfgpu
pip install -r requirements.txt
python run.py
```
Backend runs at `http://127.0.0.1:8000`.

### C. Frontend Setup (React + Vite)
```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```
Open `http://localhost:5173` in your browser.

*(Or double-click `start.bat` after initial install.)*

---

## 2. Connect Your LinkedIn Account (Free Official OAuth)
1. Go to the [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps) and click **Create App** (free).
2. Under **Products**, request/add:
   - **Sign In with LinkedIn using OpenID Connect**
   - **Share on LinkedIn** (grants `w_member_social`)
3. Under **Auth**, add Authorized Redirect URL:
   ```
   http://localhost:8000/api/connectors/linkedin/callback
   ```
4. Copy `.env.example` to `.env` in the project root and fill in `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET`.
5. Restart the backend, open **Platform Connectors** in the app, and click **Connect LinkedIn via Official OAuth**.

---

## 3. Adding Future Platforms
1. Create a new connector file in `backend/app/connectors/<platform>.py` inheriting `PlatformConnector` from `backend/app/connectors/base.py`.
2. Register it in `backend/app/connectors/registry.py`.
3. It automatically appears in the **Platform Connectors** tab and can be used by the post/comment/chat services.

---

## 4. Backup
All your data (CV, project notes, drafts, job applications, and encrypted tokens) is stored locally in `data/app.db` and `data/uploads/`. Copy the `data/` folder to back up everything.
