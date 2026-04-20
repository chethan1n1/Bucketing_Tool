# Bucketing Assistant

A premium SaaS-quality application for intelligent classification and bucketing. Uses hybrid fuzzy matching, sentence-transformer embeddings, and DB-only bucket selection. Each factor receives independent bucket classification.

## 🎯 Features

- **Hybrid Matching**: RapidFuzz plus sentence-transformer embeddings against the Excel database
- **Confidence Scoring**: Multi-component scoring across category alignment, factor similarity, and bucket support
- **AI Guardrail**: Groq only chooses from already-existing DB bucket names
- **Multi-Factor Support**: Process multiple factors independently with per-factor bucket results
- **Premium UI**: Modern, minimal SaaS-quality interface with dark mode and smooth interactions
- **Responsive Design**: Works seamlessly on desktop and mobile

## 📋 Architecture

```
User Input (Category + Factors)
    ↓
FastAPI Backend (http://127.0.0.1:8000)
    ↓
Hybrid Retrieval (RapidFuzz + Sentence Transformer Embeddings)
    ↓
Composite Confidence Calculation
  ├─ Category alignment
  ├─ Factor semantic similarity
  ├─ Bucket semantic support
  └─ Bucket-level support bonus
    ↓
Decision
├─ ✅ Confidence passes → Return Database Match bucket
└─ ❌ Any gate fails → Call Groq AI to choose from DB buckets only
    ↓
Response with Per-Factor Results
    ↓
Frontend (http://127.0.0.1:5500)
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** installed
- **Excel file** at `backend/data/Master_DB_Clean.xlsx`
- **Groq API key** (get one free at https://console.groq.com)

### Setup

1. **Clone or navigate to the project**:
   ```bash
   cd Bucketing
   ```

2. **Create Python virtual environment** (one-time):
   ```bash
   python -m venv backend/venv
   ```

3. **Activate virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     backend\venv\Scripts\Activate.ps1
     ```
   - **Windows (Command Prompt)**:
     ```cmd
     backend\venv\Scripts\activate.bat
     ```
   - **Mac/Linux**:
     ```bash
     source backend/venv/bin/activate
     ```

4. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

5. **Configure Groq API key**:
   - Create `backend/.env` file with:
     ```
     GROQ_API_KEY=your_api_key_here
     ```

## ▶️ Running the Application

### Fast Run (Windows PowerShell)

Use this when you want to start both services quickly from the project root:

```powershell
# Terminal 1 (Backend) - IMPORTANT: run from backend folder
cd backend
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2 (Frontend) - from project root
cd ..
python -m http.server 5500 --directory frontend
```

Why this matters:
- `loader.py` reads `data/Master_DB_Clean.xlsx` using a relative path.
- Backend must be started from `backend/` so `data/...` resolves correctly.

Open:
- Frontend: **http://127.0.0.1:5500**
- Backend docs: **http://127.0.0.1:8000/docs**

### Terminal 1: Start Backend Server

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

This starts the API server on **http://127.0.0.1:8000**

**Expected output**:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Terminal 2: Start Frontend Server

```bash
python -m http.server 5500 --directory frontend
```

This serves the frontend on **http://127.0.0.1:5500**

**Expected output**:
```
Serving HTTP on 127.0.0.1 port 5500
```

### 3. Open in Browser

Navigate to **http://127.0.0.1:5500** and start classifying!

### Optional: One-liner launch (detached)

If you want both servers launched in the background from one PowerShell command:

```powershell
Start-Process -FilePath ".\backend\venv\Scripts\python.exe" -ArgumentList @("-m","uvicorn","main:app","--host","127.0.0.1","--port","8000") -WorkingDirectory ".\backend"; Start-Process -FilePath "python" -ArgumentList @("-m","http.server","5500","--directory","frontend") -WorkingDirectory "."
```

## 📁 Project Structure

```
Bucketing/
├── backend/
│   ├── venv/                          # Python virtual environment
│   ├── data/
│   │   └── Master_DB_Clean.xlsx       # Database file (your data)
│   ├── main.py                        # FastAPI application
│   ├── loader.py                      # Excel data loader
│   ├── matcher.py                     # Hybrid matching engine
│   ├── utils.py                       # AI bucket guardrail utilities
│   ├── requirements.txt               # Dependencies
│   └── .env                           # Groq API key (not in git)
└── frontend/
    ├── index.html                     # Main UI
    ├── app.js                         # JavaScript logic
    └── style.css                      # Modern styling
└── README.md                          # This file
```

## 🔧 How It Works

### 1. **Data Loading** (`loader.py`)
- Reads Excel file from `backend/data/Master_DB_Clean.xlsx`
- Normalizes column names and data types
- Supports: `category`, `factor`, `bucket` columns

### 2. **Matching Engine** (`matcher.py`)
- **Normalization**: Removes special characters, standardizes whitespace, lowercases text
- **Fuzzy Matching**: Uses a composite RapidFuzz score (`ratio`, `partial`, `token_sort`, `token_set`, `WRatio`)
- **Semantic Matching**: Sentence-transformer embeddings rank factor similarity and category alignment
- **Bucket Intelligence**: Bucket centroids and bucket support boost consistent DB-backed decisions
- **Per-Factor Processing**: Each factor is matched independently

### 3. **Threshold Gating**
```python
HIGH_CONFIDENCE = 0.8
MEDIUM_CONFIDENCE = 0.6
SHORT_CIRCUIT_EMBEDDING = 0.9
```

- ✅ If confidence is strong → Return database bucket result
- ❌ If confidence is weaker → Use Groq only as a selector among existing DB buckets

### 4. **AI Fallback** (`utils.py`)
- Calls Groq API (llama-3.3-70b-versatile)
- Only accepts bucket names that already exist in the database
- Normalizes model output before validating against the allowed bucket list
- Falls back to `UNMAPPED_REVIEW_REQUIRED` when no DB bucket is safe to use

### 5. **API Response Format**
```json
{
  "category": "finance",
  "results": [
    {
      "factor_input": "risk of money",
      "source": "database",
      "category": "finance",
      "factor": "risk of money",
      "bucket": "Risk Metrics",
      "confidence_score": 0.91,
      "final_score": 0.91,
      "embedding_score": 0.96,
      "fuzz_score": 0.88
    },
    {
      "factor_input": "trust",
      "source": "ai",
      "bucket": "Trust Factors",
      "category": "finance",
      "factor": "trust"
    }
  ]
}
```

## 🎨 Frontend Features

- **Minimal, Modern Design**: Swiss design principles with clean typography
- **Dark Mode**: Toggle between light/dark (respects system preference)
- **Auto-Resizing Textarea**: Grows as you type
- **Real-Time Validation**: Button only enabled with valid input
- **Keyboard Shortcuts**:
  - `Cmd/Ctrl+K` → Focus category field
  - `Enter` in category → Jump to factors
  - `Ctrl+Enter` in factors → Submit
- **Smooth Animations**: Fade-in, slide-up transitions (0.2-0.3s)
- **Responsive**: Works on mobile, tablet, desktop

### Result Display
- Clean table format (Factor | Source | Bucket)
- Color-coded badges: 🟢 Database | 🟣 AI
- Highlighted bucket names
- Quick "New Classification" button

## 🔐 Environment Variables

Create `backend/.env`:
```
GROQ_API_KEY=gsk_your_key_here
```

Get a free key at: https://console.groq.com/keys

## 📊 Excel Database Format

Your `Master_DB_Clean.xlsx` should have columns:
| category | factor | bucket |
|----------|--------|--------|
| Finance | Risk of Money | Risk Metrics |
| Finance | Trust | Trust Factors |
| Insurance | Claims | Claims Processing |

Column names are case-insensitive and auto-normalized.

## 🧪 Testing

### Test with Frontend
1. Start both servers (see [Running the Application](#-running-the-application))
2. Open http://127.0.0.1:5500
3. Try:
   - **Known input**: Category that matches your Excel data
  - **Unknown input**: Random category to trigger DB-only AI bucket selection

### Test via API (PowerShell)
```powershell
$body = @{
    category = "Finance"
    factors = @("Risk of money", "Trust")
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/predict" `
    -Method POST `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body

$response | ConvertTo-Json -Depth 5
```

## 🐛 Troubleshooting

### Backend won't start
```
ModuleNotFoundError: No module named 'fastapi'
```
- **Fix**: Make sure virtual environment is activated and `pip install -r requirements.txt` was run

### Frontend can't reach backend
```
Could not connect to the backend. Make sure the server is running on port 8000.
```
- **Fix**: Check that backend server is running on http://127.0.0.1:8000
- **Fix**: Check firewall settings, ensure port 8000 is not blocked

### Groq API returns error
```
401 Unauthorized
```
- **Fix**: Check that `GROQ_API_KEY` in `.env` is correct
- **Fix**: Regenerate key at https://console.groq.com/keys

### Results show wrong bucket
- **Fix**: Check confidence scores in API response
- **Fix**: Adjust `HIGH_CONFIDENCE`, `MEDIUM_CONFIDENCE`, `SHORT_CIRCUIT_EMBEDDING` in `backend/main.py`
- **Fix**: Verify data in Excel file is correct

## 📦 Dependencies

### Backend
- **fastapi** - Modern web framework
- **uvicorn** - ASGI server
- **pandas** - Data manipulation
- **openpyxl** - Excel support
- **rapidfuzz** - Fuzzy matching
- **groq** - AI API client
- **python-dotenv** - Environment variables

### Frontend
- Vanilla HTML, CSS, JavaScript (no external libraries)

## 🚀 Deployment

For production, consider:
1. Use Gunicorn/Waitress instead of Uvicorn development server
2. Deploy frontend to CDN or static host
3. Add authentication/authorization
4. Set up logging and monitoring
5. Configure CORS for your domain

## 📝 License

This project is for internal use.

## 💬 Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review backend logs for error details
3. Check browser console (F12) for frontend errors
