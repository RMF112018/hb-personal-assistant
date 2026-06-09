# Supporting Context

## User requirement

Bobby stated:

> I want to be sure the current logic captures modified date/time and modified by user names. It is critical that the project reference, folder name, file name, modified date/time, and modified by user names are stored as raw content.

## Current repo-truth assumption to verify

Prior audit indicated:

- file name is captured;
- folder/path metadata is captured;
- modified date/time is captured;
- project/source reference is partially captured;
- modified-by user names are not first-class captured/persisted.

The local agent must verify this before implementation.

## Important distinction

The requested fields are raw operational metadata, not full document body content.

This package does not request:

- reading PDF/Word/Excel contents;
- storing full document text;
- OCR;
- embeddings;
- document summarization.

## Raw boundary

Local SQLite DB may store raw operational metadata needed for the product.

Committed evidence must remain redacted/safe.
