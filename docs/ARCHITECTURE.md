# StupidClaw Architecture — Definitive Design

## Core Principle
**Put intelligence in the system, not the model.**

## The 8 Laws

### 1. Cascade, Not One Path
Router classifies: easy | medium | hard
- **Easy:** one pass, direct answer
- **Medium:** retrieve → answer with evidence
- **Hard:** 3 parallel attempts, different evidence/prompts, one reducer

### 2. Disciplined Swarm (Committee of Clones)
Same small model, 3 diverse attempts, one judge/scorer.
NOT: recursive debate, free-form agent chat, town halls.

### 3. Exploit Cheapness
Small models can be sampled 5x for the price of 1 big model call.
draft → retrieve query → answer → verify → rewrite = inference-time scaling without weight changes.

### 4. Pull-Based Context
DO NOT dump memory, tools, history into prompt.
Show tiny index/summary → model requests chunk IDs, facts, tool schemas on demand.
(CoLoR: 1.9x compression. ACC-RAG: 4x faster. ECoRAG: explicit "is this enough?" loop)

### 5. FSM States, Not Agent Personas
States: classify → plan → act → verify → respond
Each state gets: tiny prompt, tiny tool list, strict output schema.
(MetaAgent 2025: FSM control is a serious design pattern)

### 6. Verification = First-Class Stage
Verifier asks: "unsupported / sufficient / contradictory?"
Answer ONLY from evidence. Check sufficiency BEFORE proceeding.
(SelfCite: best-of-N for attribution. ECoRAG: explicit evidence sufficiency control)

### 7. Optimize Prompts Like Software
Treat prompt/workflow choice as a search problem.
Build eval set from real tasks → tune prompts, tool descriptions, temperatures.
(AutoPDL: automated optimization over Zero-Shot, CoT, ReAct, ReWOO)

### 8. Specialization by Aperture
Same model, different operating modes:
- different toolset
- different schema
- different max context
- different stopping rules

Hospital triage desk: grill station isn't smarter than expeditor, just narrower job.

## The Pipeline

```
User Message
    ↓
[ROUTER] → easy | medium | hard (tiny classifier, ~100 tokens)
    ↓
EASY ────→ one pass answer → verify → respond
MEDIUM ──→ retrieve 3 chunks → answer with evidence tags → verify → respond  
HARD ────→ 3 parallel clones (different evidence/prompt) → judge/score → final writer → verify → respond
```

## Highest-ROI Combo
**cascade routing + pull-based context + committee-of-clones + verification gate**
