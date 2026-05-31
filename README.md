# 🤖 AI SQL Assistant with LangChain + Multilingual RAG

> Ask questions in any language. Get accurate SQL back. Instantly.

Built with **LangChain**, **PostgreSQL**, **Streamlit**, **NVIDIA NIM**, and a **Multilingual RAG layer** powered by `BAAI/bge-m3` embeddings and ChromaDB — enabling schema-aware, business-aware SQL generation across 100+ languages.

---

## ✨ Features

- 💬 Natural language to SQL — in any language (English, Hindi, French, Spanish, and 100+ more)
- 🌍 Multilingual RAG layer using `BAAI/bge-m3` cross-lingual embeddings
- 🗄️ Connects to any PostgreSQL database
- 🧠 Powered by NVIDIA NIM's free Mistral Large 3 endpoint
- ⚡ LangChain SQL Agent for multi-step query reasoning
- 🔍 Dynamic schema retrieval — only relevant tables injected into the prompt
- 📖 Explainable SQL — see which tables, columns, and context chunks drove the query
- 📊 Auto chart suggestions powered by Plotly / Altair
- 🔒 SQL guardrails blocking destructive operations (DROP, DELETE, TRUNCATE, ALTER, UPDATE)
- 🖥️ Clean Streamlit UI with generated SQL display toggle

---

## 🗂️ Project Structure

```
ai-sql-assistant/
├── app.py                  # Streamlit UI
├── db.py                   # PostgreSQL connection & schema loader
├── chain.py                # LangChain SQL agent setup
├── prompts.py              # Custom prompt templates
├── seed_index.py           # One-time script to populate the vector store
│
├── rag/
│   ├── embeddings.py       # NVIDIA NIM BGE-M3 embedding wrapper
│   ├── retriever.py        # Top-K schema retrieval via cosine similarity
│   ├── vector_store.py     # ChromaDB client initialisation
│   ├── indexing.py         # Chunking & indexing pipeline
│   ├── language_detector.py# Detects query language (langdetect)
│   ├── context_builder.py  # Assembles retrieved context for the prompt
│   └── sql_guardrails.py   # Blocks destructive SQL before execution
│
├── knowledge/
│   ├── schema_docs/        # One markdown file per table
│   ├── business_rules/     # Business logic definitions
│   ├── glossary/           # Term definitions (revenue, churn, etc.)
│   └── kpi_definitions/    # KPI documentation (MAU, LTV, etc.)
│
├── vector_db/              # ChromaDB persistent store (auto-created)
│
├── .env                    # API keys & DB credentials (never commit this)
├── .env.example            # Example env file — safe to commit
├── requirements.txt        # Python dependencies
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

### 5. Populate the knowledge base

Add one markdown file per table inside `knowledge/schema_docs/`. Example for a `customers` table:

```markdown
# Table: customers
Description: Stores all registered customer records.
Columns: customer_id (PK), name, email, created_at
Relationships: customers.customer_id → orders.customer_id
```

Then seed the vector index (run once):

```bash
python seed_index.py
```

### 6. Run the app

```bash
streamlit run app.py
```

---

## 🧠 Models Used

| Model | Provider | Purpose | Endpoint |
|-------|----------|---------|----------|
| `mistralai/mistral-large-3-675b-instruct-2512` | Mistral AI via NVIDIA NIM | SQL generation & reasoning | ✅ Free API |
| `BAAI/bge-m3` | BAAI via NVIDIA NIM | Multilingual embeddings & retrieval | ✅ Free API |

---

## ⚙️ How It Works

```
User Question (any language)
        ↓
Language Detection (langdetect)
        ↓
BGE-M3 Multilingual Embedding
        ↓
ChromaDB Vector Search (cosine similarity, top-5)
        ↓
Schema Context + Business Definitions Retrieved
        ↓
Context Assembly → LangChain SQL Agent
        ↓
NVIDIA NIM API (Mistral Large 3 — 675B)
        ↓
SQL Query Generated
        ↓
SQL Guardrails Validation
        ↓
Executed on PostgreSQL
        ↓
Result + Explanation + Chart displayed in Streamlit UI
```

---

## 📦 Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit |
| LLM Orchestration | LangChain |
| LLM API | NVIDIA NIM — Mistral Large 3 (Free Tier) |
| Embedding Model | NVIDIA NIM — BAAI/bge-m3 (Free Tier) |
| Vector Store | ChromaDB |
| Language Detection | langdetect |
| Database | PostgreSQL |
| ORM / DB Connector | SQLAlchemy + psycopg2 |
| Visualisation | Plotly + Altair |
| Config | python-dotenv |

---

## 🌍 Multilingual Query Examples

All of the following retrieve identical schema context and generate equivalent SQL:

| Language | Query |
|----------|-------|
| English | Show top 10 customers by revenue |
| Hindi | राजस्व के अनुसार शीर्ष 10 ग्राहक दिखाओ |
| French | Montrez les 10 meilleurs clients par revenus |
| Spanish | Mostrar los 10 principales clientes por ingresos |

---

## 📝 Example Queries

| Plain English | Generated SQL |
|---------------|--------------|
| How many users signed up last month? | `SELECT COUNT(*) FROM users WHERE created_at >= date_trunc('month', NOW() - INTERVAL '1 month')` |
| Top 5 products by revenue | `SELECT product_name, SUM(price) AS revenue FROM orders GROUP BY product_name ORDER BY revenue DESC LIMIT 5` |
| List all orders that are still pending | `SELECT * FROM orders WHERE status = 'pending'` |

---

## 🔒 Security Notes

- Never commit your `.env` file — it is listed in `.gitignore`
- Use a **read-only** PostgreSQL user for safety
- Restrict `SQLDatabase.from_uri()` to specific tables using `include_tables=[...]` to limit schema exposure
- SQL guardrails in `rag/sql_guardrails.py` block `DROP`, `DELETE`, `TRUNCATE`, `ALTER`, and `UPDATE` by default

---

## 🛠️ Customization

**Change the LLM** — in `chain.py`:
```python
model="meta/llama-4-maverick-17b-128e-instruct"  # lighter, faster
model="google/gemma-3-27b-it"                    # multimodal support
```

**Restrict tables** — in `db.py`:
```python
SQLDatabase.from_uri(db_url, include_tables=["orders", "users", "products"])
```

**Adjust RAG retrieval count** — in `rag/retriever.py`:
```python
TOP_K = 5  # increase for larger schemas, decrease to reduce token usage
```

**Enable destructive queries** (use with caution) — in `rag/sql_guardrails.py`:
```python
ALLOW_MUTATIONS = True  # disabled by default
```

---

## ⚡ Performance Targets

| Operation | Target |
|-----------|--------|
| Embedding generation | < 1 second |
| Vector retrieval | < 500 ms |
| SQL generation | < 5 seconds |
| End-to-end response | < 8 seconds |

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙌 Acknowledgements

- [NVIDIA NIM](https://build.nvidia.com) — Free LLM & embedding inference API
- [Mistral AI](https://mistral.ai) — Mistral Large 3 model
- [BAAI](https://huggingface.co/BAAI/bge-m3) — BGE-M3 multilingual embedding model
- [LangChain](https://python.langchain.com) — LLM orchestration framework
- [ChromaDB](https://www.trychroma.com) — Open-source vector database
- [Streamlit](https://streamlit.io) — UI framework