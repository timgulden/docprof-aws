# DocProf - M&A Expert Instance Context Summary

_Last updated: 2025-11-19_

## Project Overview

**DocProf** is a Retrieval-Augmented Generation (RAG) platform that creates domain-specific expert systems by ingesting textbooks and educational materials. Each instance of DocProf is configured with a specific corpus to become an expert in that domain.

**M&A Expert** is this specific instance of DocProf, focused on teaching valuation and investment banking topics. The same DocProf platform can be loaded with different document sets to create other experts, such as:
- Computational Social Science Expert
- Data Visualization with Python Expert
- Or any other domain with appropriate textbooks

## Project Snapshot
- **Platform:** DocProf (RAG-based expert system framework)
- **Instance:** M&A Expert (valuation and investment banking focus)
- **Goal:** Build a Retrieval-Augmented Generation (RAG) "M&A Expert" that teaches and quizzes users on valuation and investment banking topics using 3–5 core textbooks.
- **Modalities:** Conversational Q&A, adaptive courses (structured learning paths with sections), quizzes, and audio lectures (AI professor persona, OpenAI TTS Onyx voice).
- **Initial Corpus:** Start with `source-docs/Valuation8thEd.pdf`; expand to additional textbooks after pipeline validation.
- **Data Store:** PostgreSQL with pgvector; recommend a dedicated `mna_expert` database on the existing instance.

## Key Documents & Where to Start
| Purpose | Location | Notes |
|---------|----------|-------|
| Functional specification & workflows | `docs/functional-spec/mna-expert-system-functional-spec.md` | Core product vision, feature matrix, success metrics. |
| Architecture principles (functional FP) | `docs/architecture/functional-architecture-summary.md` | Defines pure logic layer, command/effect separation, interceptor/decorator usage. |
| Interceptor reference | `docs/architecture/interceptor-patterns.md` | Explains both stack-based and middleware-style patterns. See also `interceptor101.md` (stack-based) and `src/interceptors/common.py` (middleware-style). |
| Ingestion pipeline guide | `docs/implementation/ingestion-pipeline-guide.md` | PDF → chunks → embeddings → database workflow. |
| Database schema | `docs/implementation/database-schema-and-setup.md` | pgvector schema, sample queries, setup scripts. |
| Backend guide | `docs/implementation/fastapi-backend-guide.md` | REST interface, dependency wiring, session management via pure logic. |
| Frontend guide | `docs/implementation/react-frontend-guide.md` | React/TypeScript structure, state management, UI components. |
| Course system guide | `docs/implementation/course-system-implementation-guide.md` | Course generation, section-based lectures, progress tracking. |

## Architecture at a Glance
- **Functional Core / Imperative Shell:** Logic layer returns `(new_state, commands)`; effects layer executes commands (LLM, DB, TTS) via interceptors/decorators.
- **State Management:** Immutable Pydantic models (`model_copy`) for application state; no in-place mutation; configuration passed through closures.
- **Interceptors:** Stack-based pipeline for cross-cutting concerns (logging, persistence, cost tracking) and command orchestration.
- **Storage:** Text/figure chunks with embeddings in pgvector; progress, quizzes, audio metadata tracked in relational tables.

## Usage Tips for New Sessions
- Start by skimming the functional spec, then read `functional-architecture-summary.md` to understand design constraints.
- When implementing features, align logic with the interceptor/command pattern; keep side effects confined to effects modules.
- For ingestion tasks, follow the step-by-step Python code in `ingestion-pipeline-guide.md`; adjust parameters (chunk overlap, figure filters) per the initial PDF.
- Update the “Last updated” line whenever major context changes so future sessions know how fresh this summary is.
- Activate the project virtual environment before running commands. Add this alias to your shell profile (e.g. `~/.zshrc`) and use it for every session:  
  ```bash
  alias workon-maexpert='cd "/Users/tgulden/Documents/AI Projects/MAExpert" && source .venv/bin/activate'
  ```  
  Then run `workon-maexpert` to enter the repo with the venv active.
- Figure search results now include structured fields (`description_text`, `key_takeaways`, `use_cases`, `image_url`) and are backed by `/api/figures/{figure_id}/image`, which streams the stored PNG/JPEG from PostgreSQL.
- Git remote: `origin` → `https://github.com/timgulden/maexpert.git`; default branch `main`. Push flow: `git add <files> && git commit -m "<msg>" && git push`.

