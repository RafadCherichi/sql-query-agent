PROJECT: Agentic LLM Workflow — Text-to-SQL Data Query Agent
PORTFOLIO: Project 2 of 7 in a PM+ML applied AI portfolio (Project 1, RAG
Feedback Analyzer, is complete — same documentation rigor applies).

HARDWARE PROFILE:
- Total system RAM: 8GB. Free RAM is often as low as ~2GB depending on what
  else is running — treat this as the binding constraint, not the 8GB total.
- GPU: NVIDIA RTX 3050, 4GB VRAM. Use Ollama's GPU offload so the model runs
  mostly on VRAM, not system RAM.
- No local model training/fine-tuning in this project — inference only. If a
  future project needs fine-tuning, that goes on Colab/Kaggle's free GPU
  tier, not this laptop.

STRICT CONSTRAINTS:
- Budget: $0. No paid APIs, no paid vector DBs, no paid eval/observability tools.
- Data: Chinook database only for v1 (publicly available, near-zero setup).
  No synthetic or custom-curated data. Olist is a planned v2 upgrade, not
  part of v1 scope.
- Pattern: use the established LangGraph text-to-SQL ReAct pattern
  (list_tables / get_schema / run_query tools + self-correction on error).
  Do not invent a novel architecture — the goal is demonstrated competence
  with a proven pattern.
- Model: Qwen2.5-3B-Instruct, Q4_K_M quantization, via Ollama, GPU-offloaded.
  Confirm free system RAM before loading anything larger.
- Reliability priority: must run smoothly end-to-end with no live external
  API dependency in the agent loop itself (SQLite is local/offline once the
  Chinook .db file is in place).
- Working style: propose options with pros/cons + a recommendation for any
  nontrivial decision, wait for confirmation before proceeding. Maintain
  CLAUDE.md and docs/blueprint.md as persistent project memory.

See docs/blueprint.md for the full Master Execution Blueprint (phases,
architecture, eval plan, portfolio strategy).
