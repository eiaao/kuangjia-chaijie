# kuangjia-chaijie · Framework Topic Decomposition Workflow

**Understand a framework deeply — completely and gap-free — before you write or present about it.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-skill-d97757.svg)](https://docs.claude.com/en/docs/claude-code)
![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)

English | [中文](./README.zh.md)

> **This skill does not output an article. It outputs "complete, out-loud-recountable understanding."**
> Input: a framework/codebase + a topic word　→　Output: 4 (+1 optional) structured markdown documents.
> Writing the article is what happens *after* the skill finishes.

For anyone preparing a tech talk, a deep-dive article, or a team session: before you start writing, get a cross-module topic **complete, clear, and gap-free** in your head first.

---

## The problem it solves

Three failure modes dominate when reading framework source:

1. **Guessing** — filling gaps with "usually / typically / by convention" from training-data patterns, which often differ from how *this* project is actually implemented.
2. **Missing** — the topic spans modules; a top-down scan based on current understanding can't catch modules hidden mid-file in a large file, or on a background path off the main loop.
3. **Drifting** — shallow reads produce shallow conclusions, and self-review skips over what you already wrote, so errors survive to the end.

This skill counters them with an agentic pipeline: **top-down (project mental-model scan) + bottom-up (symbol back-tracing) in tandem**, mandatory human-in-the-loop checkpoints for scope, hard exit criteria per phase, and cross-verification of every phase's output by a **clean-context subagent** against the source.

---

## When to use / not use

✅ Use it when
- Preparing a tech talk / article / team session but not yet on top of the topic
- The topic spans multiple modules (not explainable from a single file)
- You want "complete, no gaps" understanding of a module

❌ Don't use it for
- Single-file / single-function questions → just Read / Grep
- Debugging a specific bug → use a debugging skill
- Designing a new feature → use brainstorming → writing-plans

---

## Pipeline (4 phases + 1 optional)

| Phase | What | Output | Exit gate (excerpt) |
|---|---|---|---|
| **0 Seeding** | Turn a fuzzy topic word into a "seed card" | `00-seed.md` | ≥5 keywords, ≥2 explicit exclusions |
| **1 Panorama (A+B)** | Mental model + symbol heatmap + cross-check + panorama + reverse coverage + blind-spot review | `01-*.md` | 5–9 modules, ≥2 Mermaid diagrams, subagent-verified, user sign-off |
| **2 Per-module deep dive** | A "7-element card + design trade-offs + retro" per module | `02-S{n}-{slug}.md` (one each) | All 10 blocks filled, lifecycle diagram, subagent-verified |
| **3 Re-unification** | v0→v1, architecture diagram, cross-module patterns, cross-card conflicts, upstream backfill | `03-synthesis.md` | One-sentence essence, ≥2 cross-module patterns, conflicts explicitly resolved, backfill table processed |
| **4 Evolution archaeology (optional)** | Pick modules by interest; funnel-style git archaeology of "how it became what it is" | `04-evolution-S{n}-{slug}.md` | Timeline diagram + inflection points with commit hashes + why, stability annotations |

---

## Four core principles

1. **Don't guess → Read first → then ask.** Every conclusion needs evidence (code/docs/data you read, or what the user explicitly told you). Words like "usually / generally / should / likely" trigger a stop: either go Read for evidence or mark `[to clarify: ...]`.
2. **Visualization is mandatory.** Plain text + tables don't count; each phase needs at least one Mermaid diagram — drawing is the most efficient blind-spot finder, and a connection you can't draw is a real gap.
3. **Clean-context subagent verification.** Each phase's output goes to a subagent that has "never seen this card" to check claims against source line by line. Same context = same blind spots; main-agent self-verification is no verification.
4. **A feedback loop, not a one-way pipe.** After each phase, revisit upstream outputs; apply the Amend rules for any errors found (small fixes in place, structural revisions logged in amendments, abstraction shifts via v0→v1).

---

## Install

### Option 1: Plugin marketplace (recommended)

In Claude Code, run:

```bash
/plugin marketplace add eiaao/kuangjia-chaijie
```

Then **Browse and install plugins** → `kuangjia-chaijie` → Install.

### Option 2: Manual

Copy the skill directory into Claude Code's skills folder:

```bash
git clone https://github.com/eiaao/kuangjia-chaijie.git
cp -r kuangjia-chaijie/skills/kuangjia-chaijie ~/.claude/skills/
```

---

## Usage

Just tell Claude your topic, e.g.:

- "I want to deep-dive the memory architecture of the Hermes framework"
- "Help me get clear on LangChain's tool-calling mechanism"
- "I'm writing an article about part of framework XX — sort it out for me first"
- "Give me the panorama of XX first"

The skill starts at Phase 0 and pauses at checkpoints for you to confirm scope. Outputs land by default in `notes/kuangjia-chaijie/{topic-slug}/` under the project root.

---

## Layout

```
kuangjia-chaijie/
├── .claude-plugin/marketplace.json   # plugin marketplace manifest
├── skills/kuangjia-chaijie/
│   ├── SKILL.md                      # the workflow itself
│   └── assets/
│       ├── build_view.py             # renders output .md into a single-page HTML view
│       └── template.html             # HTML view template
├── README.md                         # English (this file)
└── README.zh.md                      # Chinese
```

`assets/build_view.py` aggregates each phase's markdown outputs into an interactive single-page `view.html` (markdown stays the source of truth; the HTML is just a view layer, gitignored).
