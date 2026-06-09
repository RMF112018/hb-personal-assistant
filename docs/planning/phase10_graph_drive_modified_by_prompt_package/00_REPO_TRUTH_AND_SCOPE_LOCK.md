# 00 — Repo Truth and Scope Lock

## Objective

Verify the current repository, branch, schema, and existing SharePoint/OneDrive file intelligence surfaces before making any code changes.

This is an audit-only prompt. Do not modify code.

## Required branch checks

Run:

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
```

Report:

- current branch;
- current HEAD;
- dirty tree;
- whether current commit is contained on main;
- whether main is untouched;
- whether external tooling appears to have switched branches.

If you are not on the intended branch, stop and ask Bobby or switch only if the intended branch is unambiguous.

## Scope

The requested change is limited to SharePoint/OneDrive / Graph drive item metadata capture.

Required raw operational metadata:

- project reference;
- folder name/path;
- file name;
- modified date/time;
- modified-by user names.

Do not implement:

- full document-content extraction;
- OCR;
- embeddings;
- local model summarization;
- Procore changes;
- email/calendar changes;
- UI redesign;
- production packaging;
- scheduler work.

## Repo surfaces to locate

Search and inspect all relevant files for:

- Graph files / SharePoint / OneDrive endpoints;
- drive item indexer;
- drive item normalizer;
- drive item bridge;
- source location policy;
- schema/migrations;
- repository methods;
- CLI commands;
- tests and evidence.

Suggested commands:

```bash
grep -R "drive_item" -n src tests docs resources | head -200
grep -R "lastModifiedDateTime\|lastModifiedBy\|modified_by\|modifiedBy" -n src tests docs resources | head -200
grep -R "OneDrive\|SharePoint\|Graph files\|Files.Read" -n src tests docs resources | head -200
```

## Audit output

Produce a concise audit with:

1. branch/HEAD/tree status;
2. current schema head;
3. relevant files found;
4. relevant tables found;
5. whether modified date/time is captured;
6. whether modified-by is captured;
7. implementation gap list;
8. planned prompt sequence status;
9. stop conditions, if any.

## Commit behavior

No commit in this prompt.
