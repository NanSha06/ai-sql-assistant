# INSTRUCTIONS.md

# AI SQL Assistant - Development Protection Guidelines

## Purpose

This document defines the non-negotiable architectural and implementation constraints for the AI SQL Assistant project.

Any future modifications, enhancements, refactoring, optimizations, or feature additions MUST preserve the core functionality and architecture described below.

The primary goal of this project is:

> Convert natural language questions into accurate SQL queries using a LangChain-powered agent, execute them against a PostgreSQL database, and display the results through a Streamlit interface.

Any change that compromises this workflow is considered a breaking change.

---

# Core Architecture (Must Not Be Broken)

The following flow must always remain functional:

User Question
→ Streamlit UI
→ LangChain SQL Agent
→ Schema-Aware Prompt
→ NVIDIA NIM LLM
→ SQL Generation
→ PostgreSQL Execution
→ Results Returned to User

Every future enhancement must integrate into this workflow without disrupting it.

---

# Critical Files and Responsibilities

## app.py

Responsible for:

* Streamlit UI
* User input collection
* Result display
* SQL display toggle

Do Not:

* Move business logic into UI layer
* Add direct database logic inside UI
* Add prompt engineering logic here

UI must remain separate from database and LLM layers.

---

## db.py

Responsible for:

* PostgreSQL connection
* Schema extraction
* Database utility functions

Do Not:

* Add LLM logic
* Add UI logic
* Hardcode credentials

Database layer must remain isolated.

---

## chain.py

Responsible for:

* LangChain setup
* Agent creation
* Tool registration
* LLM communication

Do Not:

* Embed Streamlit components
* Hardcode schema definitions
* Move agent logic elsewhere

All LLM orchestration belongs here.

---

## prompts.py

Responsible for:

* Prompt templates
* System instructions
* SQL generation behavior

Do Not:

* Execute SQL
* Perform database operations
* Contain application state

Prompt definitions only.

---

# Non-Negotiable Functional Requirements

The following capabilities must always remain operational.

## Natural Language to SQL

Users must be able to submit plain English questions.

Example:

Show top 10 customers by revenue

Expected behavior:

Generate valid SQL.

---

## Schema Awareness

The model must receive database schema context before generating SQL.

Future modifications must not remove schema injection.

Without schema awareness, SQL quality degrades significantly.

---

## SQL Execution

Generated SQL must execute against PostgreSQL.

Any future feature must not disable query execution.

---

## SQL Visibility

Users must always have the option to inspect generated SQL.

Transparency is a core project feature.

---

## PostgreSQL Compatibility

PostgreSQL remains the primary supported database.

Additional databases may be added.

Do not remove PostgreSQL support.

---

# Security Requirements

These rules are mandatory.

## Never Commit Secrets

Never commit:

* .env
* API keys
* Database passwords
* Tokens

---

## Read-Only Database Access

Strongly recommended:

Use read-only database users whenever possible.

---

## Dangerous Query Protection

Future contributors must prevent execution of:

* DROP
* DELETE
* TRUNCATE
* ALTER
* UPDATE

unless explicitly enabled through a controlled configuration.

---

## SQL Validation Layer

Any future SQL validation system must:

* Preserve valid analytical queries
* Not interfere with SELECT statements
* Not modify generated SQL unexpectedly

---

# Extension Guidelines

Future enhancements should be additive.

Preferred extensions:

* RAG over schema documentation
* Query explanation generation
* Data visualization
* Dashboard generation
* Multi-database support
* LangGraph workflows
* Query optimization
* Caching
* Authentication
* Audit logging

Extensions must not replace the existing architecture.

They should integrate around it.

---

# Refactoring Rules

Before merging any change:

Verify:

1. Database connection works.
2. Schema loading works.
3. Agent initializes correctly.
4. SQL generation works.
5. SQL execution works.
6. Results display correctly.
7. Existing prompts remain functional.

If any item fails, the change must not be merged.

---

# Backward Compatibility

Future updates must preserve:

* Existing environment variables
* Existing database connection flow
* Existing agent initialization flow
* Existing user interaction pattern

Breaking changes require:

* Version increment
* Migration documentation
* Explicit approval

---

# Performance Requirements

Future changes should not:

* Increase startup time significantly
* Introduce unnecessary API calls
* Duplicate schema retrieval operations
* Reinitialize the LLM on every request

Prefer caching where appropriate.

---

# AI Assistant Instructions

If an AI coding assistant modifies this repository:

It must:

* Preserve the existing architecture
* Preserve file responsibilities
* Avoid rewriting working components unnecessarily
* Prefer minimal and targeted changes
* Maintain backward compatibility

Never replace core functionality unless explicitly requested.

---

# Definition of Success

A successful update:

* Adds functionality
* Improves maintainability
* Improves security
* Improves performance

while preserving the original workflow.

A failed update is any change that causes:

* SQL generation failure
* Database connection failure
* Agent failure
* Schema loading failure
* Streamlit UI failure

even if the new feature itself works.

Protect the core workflow above all else.
