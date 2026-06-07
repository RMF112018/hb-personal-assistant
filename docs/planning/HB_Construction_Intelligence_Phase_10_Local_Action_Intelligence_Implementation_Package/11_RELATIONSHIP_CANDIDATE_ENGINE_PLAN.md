# 11 Relationship Candidate Engine Plan

## Purpose

Relate records across systems so the assistant can explain why an item matters.

## Relationship types

- email thread ↔ project
- email thread ↔ calendar meeting
- calendar meeting ↔ project
- Procore record ↔ email thread
- Procore record ↔ calendar meeting
- Obsidian note ↔ project
- Daily Brief line ↔ source record
- task candidate ↔ source record
- commitment candidate ↔ source record
- Claude packet item ↔ source record

## Matching strategy

1. deterministic identifiers;
2. project keyword/domain/person signals;
3. date/time window;
4. embedding similarity;
5. local model adjudication only for uncertain candidates.

## Review rule

Low confidence and high-stakes relationships stay in review queue.
