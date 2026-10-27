# Domain Docs

How the engineering skills should consume this repository's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repository root, if it exists.
- **`GLOSSARY-MAP.md`** at the repository root, if it exists; it takes precedence over a single glossary only when the repository becomes multi-context.
- **`docs/adr/`**: read ADRs that touch the area about to be changed.

This repository uses the **single-context** layout:

- One repository-wide `GLOSSARY.md` at the root.
- Architecture decision records in `docs/adr/`.
- New domain terms belong in `GLOSSARY.md`.
- New durable architectural decisions belong in `docs/adr/` as ADRs.

## Exploration rules

1. Read the relevant glossary entries before inventing terminology.
2. Read ADRs relevant to the workflow, library, or integration being changed.
3. Treat the glossary as the vocabulary source and ADRs as the decision source.
4. Update these documents when a change introduces a durable domain term or architectural decision.
5. Do not create `GLOSSARY-MAP.md` or per-context glossaries unless this repository becomes a genuine multi-context monorepo.
