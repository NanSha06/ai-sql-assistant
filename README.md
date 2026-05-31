# 🤖 AI SQL Assistant with LangChain

> Ask questions in plain English. Get SQL queries back. Instantly.

Built with **LangChain**, **PostgreSQL**, **Streamlit**, and **NVIDIA NIM** (free tier) using the `mistralai/mistral-large-3-675b-instruct-2512` model — a state-of-the-art 675B instruction-following model available as a free API endpoint on NVIDIA NIM.

---

## ✨ Features

- 💬 Natural language to SQL conversion
- 🗄️ Connects to any PostgreSQL database
- 🧠 Powered by NVIDIA NIM's free Mistral Large 3 endpoint
- ⚡ LangChain SQL Agent for multi-step query reasoning
- 🖥️ Clean Streamlit UI with generated SQL display toggle
- 🔒 Schema-aware prompting using your actual DDL

---

## 🗂️ Project Structure

```
ai-sql-assistant/
├── app.py              # Streamlit UI
├── db.py               # PostgreSQL connection & schema loader
├── chain.py            # LangChain SQL agent setup
├── prompts.py          # Custom prompt templates
├── .env                # API keys & DB credentials (never commit this)
├── .env.example        # Example env file — safe to commit
├── requirements.txt    # Python dependencies
├── .gitignore
└── README.md
```

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/NanSha06/ai-sql-assistant.git
cd ai-sql-assistant
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

Create a `.env` file in the project root:

```bash
# Windows
type nul > .env

# macOS/Linux
touch .env
```

Add your credentials:

```env
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=postgres
DB_PASS=your_password
```

### 4. Get your NVIDIA NIM API Key (Free)

1. Go to [build.nvidia.com](https://build.nvidia.com)
2. Sign up for free — no credit card required
3. Navigate to **Models** → filter by **Free Endpoint** → select `mistral-large-3-675b-instruct-2512`
4. Click **Get API Key** and copy it into your `.env` file

### 5. Run the app

```bash
streamlit run app.py
```

---

## 🧠 Model Used

| Model | Provider | Endpoint | Size |
|-------|----------|----------|------|
| `mistralai/mistral-large-3-675b-instruct-2512` | Mistral AI via NVIDIA NIM | ✅ Free API | 675B |

Mistral Large 3 is a **state-of-the-art instruction-following model** with strong SQL generation, complex reasoning, and structured output capabilities — available as a free hosted endpoint on NVIDIA NIM.

---

## ⚙️ How It Works

```
User Question (plain English)
        ↓
LangChain SQL Agent
        ↓
Schema DDL injected into prompt
        ↓
NVIDIA NIM API (Mistral Large 3 — 675B)
        ↓
SQL Query generated
        ↓
Executed on PostgreSQL
        ↓
Result displayed in Streamlit UI
```

---

## 📦 Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit |
| LLM Orchestration | LangChain |
| LLM API | NVIDIA NIM — Mistral Large 3 (Free Tier) |
| Database | PostgreSQL |
| ORM / DB Connector | SQLAlchemy + psycopg2 |
| Config | python-dotenv |

---

## 🔒 Security Notes

- Never commit your `.env` file — it is listed in `.gitignore`
- Use a **read-only** PostgreSQL user for safety
- Restrict `SQLDatabase.from_uri()` to specific tables using `include_tables=[...]` to limit schema exposure

---

## 📝 Example Queries

| Plain English | Generated SQL |
|---------------|--------------|
| How many users signed up last month? | `SELECT COUNT(*) FROM users WHERE created_at >= date_trunc('month', NOW() - INTERVAL '1 month')` |
| Top 5 products by revenue | `SELECT product_name, SUM(price) AS revenue FROM orders GROUP BY product_name ORDER BY revenue DESC LIMIT 5` |
| List all orders that are still pending | `SELECT * FROM orders WHERE status = 'pending'` |

---

## 🛠️ Customization

**Change the model** — in `chain.py`:
```python
model="meta/llama-4-maverick-17b-128e-instruct"  # lighter, faster
model="google/gemma-3-27b-it"                    # multimodal support
```

**Restrict tables** — in `db.py`:
```python
SQLDatabase.from_uri(db_url, include_tables=["orders", "users", "products"])
```

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙌 Acknowledgements

- [NVIDIA NIM](https://build.nvidia.com) — Free LLM inference API
- [Mistral AI](https://mistral.ai) — Mistral Large 3 model
- [LangChain](https://python.langchain.com) — LLM orchestration framework
- [Streamlit](https://streamlit.io) — UI framework