# Bucketing Assistant

A premium SaaS-quality application for intelligent classification and bucketing. Uses fuzzy matching with an Excel database, falling back to AI (Groq) for unknown inputs. Each factor receives independent bucket classification.

## 🎯 Features

- **Smart Fuzzy Matching**: RapidFuzz-based text matching against Excel database
- **Confidence Scoring**: Multi-component scoring (category + factor) with threshold gating
- **AI Fallback**: Groq API integration for unmatched inputs with novel bucket enforcement
- **Multi-Factor Support**: Process multiple factors independently with per-factor bucket results
- **Premium UI**: Modern, minimal SaaS-quality interface with dark mode and smooth interactions
- **Responsive Design**: Works seamlessly on desktop and mobile

## 📋 Architecture

```
User Input (Category + Factors)
    ↓
FastAPI Backend (http://127.0.0.1:8000)
    ↓
RapidFuzz Matching (Token Set Ratio)
    ↓
Confidence Score Calculation
    ├─ Category Score ≥ 55
    ├─ Factor Score ≥ 55
    └─ Total Score ≥ 120
    ↓
Decision
├─ ✅ All gates pass → Return Database Match
└─ ❌ Any gate fails → Call Groq AI for Novel Bucket
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

### Terminal 1: Start Backend Server

```bash
cd backend
python -m uvicorn main:app --reload
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

## 📁 Project Structure

```
Bucketing/
├── backend/
│   ├── venv/                          # Python virtual environment
│   ├── data/
│   │   └── Master_DB_Clean.xlsx       # Database file (your data)
│   ├── main.py                        # FastAPI application
│   ├── loader.py                      # Excel data loader
│   ├── matcher.py                     # Fuzzy matching engine
│   ├── utils.py                       # AI fallback utilities
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
- **Fuzzy Matching**: Uses `token_set_ratio` (stricter than partial matching)
- **Scoring**:
  - `category_score` = fuzzy match with row category
  - `factor_score` = average of all input factor matches
  - `total_score` = category_score + factor_score
- **Per-Factor Processing**: Each factor is matched independently

### 3. **Threshold Gating**
```python
THRESHOLD = 120              # Minimum total score
CATEGORY_MIN_SCORE = 55      # Category must meet threshold
FACTOR_MIN_SCORE = 55        # Factors must meet threshold
```

- ✅ If ALL scores pass → Return database result
- ❌ If ANY score fails → Call Groq AI

### 4. **AI Fallback** (`utils.py`)
- Calls Groq API (llama-3.3-70b-versatile)
- Enforces novel bucket names (not in existing database)
- Retry logic: 2 attempts if model returns existing bucket
- Fallback response if retries exhausted: `"Novel_AI_Bucket"`

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
      "confidence_score": 157.14,
      "category_score": 100.0,
      "factor_score": 57.14
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
   - **Unknown input**: Random category to trigger AI

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
- **Fix**: Adjust `THRESHOLD`, `CATEGORY_MIN_SCORE`, `FACTOR_MIN_SCORE` in `backend/main.py`
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
