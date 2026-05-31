# 🤖 AI SQL Assistant with LangChain

> Ask questions in plain English. Get SQL queries back. Instantly.

Built with **LangChain**, **PostgreSQL**, **Streamlit**, and **NVIDIA NIM** (free tier) using the `nvidia/llama-3.1-nemotron-nano-8b-healthcare-text2sql-v1.0` model — purpose-built for Text-to-SQL tasks.

---

## ✨ Features

- 💬 Natural language to SQL conversion
- 🗄️ Connects to any PostgreSQL database
- 🧠 Powered by NVIDIA NIM's free Text-to-SQL model
- ⚡ LangChain SQL Agent for multi-step query reasoning
- 🖥️ Clean Streamlit UI with query display toggle
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
├── .env.example        # Example env file
├── requirements.txt    # Python dependencies
└── README.md
```

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/ai-sql-assistant.git
cd ai-sql-assistant
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=postgres
DB_PASS=your_password
```

### 5. Get your NVIDIA NIM API Key (Free)

1. Go to [build.nvidia.com](https://build.nvidia.com)
2. Sign up for free — no credit card required
3. Navigate to **API Catalog** → select any model → click **Get API Key**
4. Copy the key into your `.env` file

### 6. Run the app

```bash
streamlit run app.py
```

---

## 🧠 Model Used

| Model | Provider | Type | Size |
|-------|----------|------|------|
| `nvidia/llama-3.1-nemotron-nano-8b-healthcare-text2sql-v1.0` | NVIDIA NIM | Text-to-SQL (fine-tuned) | 8B |

This model is **fine-tuned specifically for Text-to-SQL** tasks. It accepts your table DDL as context and returns only the SQL query — fast, deterministic, and efficient.

> 🔁 You can swap to `mistralai/mistral-large-2-instruct` or `qwen/qwen3-coder-480b-a22b-instruct` for more complex multi-join queries by changing the `model` field in `chain.py`.

---

## ⚙️ How It Works

```
User Question (plain English)
        ↓
LangChain SQL Agent
        ↓
Schema DDL injected into prompt
        ↓
NVIDIA NIM API (Text-to-SQL model)
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
| LLM API | NVIDIA NIM (Free Tier) |
| Database | PostgreSQL |
| ORM / DB Connector | SQLAlchemy + psycopg2 |
| Config | python-dotenv |

---

## 🔒 Security Notes

- Never commit your `.env` file — it's listed in `.gitignore`
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
model="mistralai/mistral-large-2-instruct"  # for complex reasoning
model="qwen/qwen3-coder-480b-a22b-instruct" # for code-heavy SQL
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
- [LangChain](https://python.langchain.com) — LLM orchestration framework
- [Streamlit](https://streamlit.io) — UI framework