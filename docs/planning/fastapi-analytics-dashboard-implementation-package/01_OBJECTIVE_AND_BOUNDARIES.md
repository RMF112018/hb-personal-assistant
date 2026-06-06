# Objective and Boundaries

## Objective

Implement a FastAPI-backed UI that brings Procore, Outlook, Calendar, SharePoint, OneDrive, local read models, evidence, review items, and externally generated Daily Brief content into one low-friction construction management workspace.

The system should reduce the user's daily platform switching and information hunting. The app should refresh, aggregate, cross-reference, prioritize, and present the information so the user spends time reviewing and acting, not operating tools.

## Primary Product Definition

A single place to start the day, understand what changed, prepare for meetings, review what matters, and act quickly.

## Primary Users

- Construction Management User: PM/PX/Superintendent/Operations/Commercial/Executive user.
- Admin User: same current single user for now, but with access to backend configuration, first sync scheduling, and data confidence/troubleshooting controls.

## Chat Boundary

The in-app chat interface is future/stub-only. Do not expose a Chat navigation item, Chat page, WebSocket/SSE chat stream, active `/api/chat` behavior, model selection, or tool-calling chat surface. All conversational work occurs externally in Claude, ChatGPT, Grok, Perplexity, or similar external platforms.

## Daily Brief Boundary

Daily Brief is optional. It is generated externally by a desktop AI platform/agent as a Markdown file. The app detects the Markdown file, validates freshness, parses it where practical, and presents it in a polished executive brief format. The app is a presenter/formatter, not the author, in this implementation.

## UI Boundary

The UI must not be a graphical CLI wrapper. Backend safety mechanics may retain dry-run/apply semantics internally, but primary user labels must be business-oriented.
