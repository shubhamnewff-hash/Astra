# Astra - AI Knowledge Assistant for Biziverse

## Problem Statement
Astra is an AI-powered Knowledge Assistant for Biziverse users to quickly understand features, learn workflows, resolve common issues, and access training materials. The assistant must operate with **bank-level zero-hallucination accuracy** — only answer from the curated Knowledge Base, and never fabricate.

## Architecture
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI (relative-path API calls — REACT_APP_BACKEND_URL is intentionally empty to bypass ingress CORS)
- **Backend**: FastAPI + MongoDB (motor async)
- **AI**: OpenAI gpt-5.2 via emergentintegrations + EMERGENT_LLM_KEY
- **Auth**: JWT httpOnly cookies + bcrypt + RBAC (5 roles)

## What's Been Implemented

### Iteration 1 (June 4, 2026)
- User Portal: AI chat streaming, conversation history, feedback, tickets, announcements
- Admin Portal: Dashboard, knowledge CRUD, resource management, user management, AI config, announcements, tickets
- JWT auth with brute force protection, 5 RBAC roles

### Iteration 2 (June 4, 2026)
- Password reset flow (forgot password → token → reset)
- Knowledge gap analysis (unanswered questions tracking, accept/reject/bulk delete)
- AI optimization: MongoDB text indexes for 50K+ items, top 3 results only, compact context
- Trained answers (admin verified Q&A pairs)
- Configurable fallback (message, button text/link, raise-ticket button)

### Iteration 3 (June 4, 2026)
- CORS login fix (frontend switched to relative `/api/*` paths)
- Markdown / **bold** rendering in chat + admin editors
- Admin AI Config: suggestion message, smart-suggestion toggles, suggestion module filter, dynamic home-screen questions (manual + random modes), fallback button config
- Dashboard date filters (today / week / month / year / custom)
- Conversation Management: AI confidence badges per assistant message
- Strict "Bank-level" chat: removed Creative/Natural modes; max_score < 4 → always show suggestions; AI uncertain → override with fallback/suggestions
- General Questions: admin CRUD page + chat-side priority routing with buttons + suggestion_questions

### Iteration 5 (June 4, 2026)
- **Removed Tickets** section from admin panel entirely (nav + route). User-side "Raise Support Ticket" fallback button preserved.
- **Removed ticket icon** next to thumbs-up/thumbs-down in chat — only feedback thumbs now.
- **Clickable Dashboard cards** — each stat card is a router Link: Helpful% → /admin/feedback?filter=helpful, Not Helpful% → /admin/feedback?filter=not_helpful, Total Questions → /admin/conversations, Active Users → /admin/users, Unanswered → /admin/gap-analysis, KB Items → /admin/knowledge.
- **NEW Admin Feedback page** (/admin/feedback) — tabs All / Helpful / Not Helpful with counts, enriched rows showing question + AI response + user comment. Capped at latest 100 entries.
- **Conversation history limit** — user sidebar shows latest N (default 25, admin-configurable in AI Config → User Experience). Older conversations auto-deleted on each list call.
- **Always-visible delete button** on each conversation in the user sidebar.
- **NEW Reset Data** Danger Zone in AI Config — wipes conversations/messages/feedback/tickets/unanswered while preserving KB+users+config. Verified: wipes everything cleanly, KB+users intact.
- **Admin Conversations** capped at latest 100 with bulk-delete support: checkbox per row + select-all, orange action bar with AlertDialog confirmation; individual delete icon per row also added. New endpoints: `DELETE /api/admin/conversations/{id}` and `POST /api/admin/conversations/bulk-delete`.
- Backend: 9/9 new pytest pass. Frontend: 11/11 UI flows verified.


- **Knowledge Base Export**: `GET /api/knowledge/export` (admin-only) returns JSON snapshot of modules + topics + items + resources with counts. Admin UI: "Export KB" button on Knowledge Base page downloads `astra-kb-export-<timestamp>.json`.
- **Multilingual Astra**: auto-detect user language, translate query to English for KB matching, translate response (and suggestions, button labels, fallback) back to user language while preserving markdown and brand names (Biziverse, GST, ERP). Verified live: Hindi (Devanagari), Spanish, English baseline.
- Admin AI Config: `Multilingual (auto-translate)` switch
- `data-testid="confidence-badge"` added for testability
- 47/47 backend pytest passing; KB export + multilingual + general questions + bank-level regression verified

## Testing Status
- Backend: 47/47 pytest (iter1, iter3, iter4) ✓
- Frontend: KB Export, Multilingual toggle, General Questions, Conversations list, Markdown rendering all verified via testing agent

## Prioritized Backlog

### P1
- [ ] Streaming KB export (NDJSON / Content-Disposition header) for very large KBs
- [ ] Validate General Question payloads with Pydantic models (triggers, buttons)
- [ ] Cache language detection for short repeated messages to reduce LLM cost on multilingual traffic
- [ ] Email-based password reset (instead of token in response)

### P2
- [ ] Bulk import knowledge items (counterpart to Export)
- [ ] KB Import endpoint to restore from exported JSON
- [ ] Mobile responsive improvements
- [ ] Per-conversation language indicator in admin Conversation view

### P3
- [ ] Analytics: per-language usage breakdown
- [ ] Voice input (whisper) for chat
- [ ] Slack / Teams integration

## Key API Endpoints
- `POST /api/auth/login` — admin@biziverse.com / Admin@123
- `POST /api/chat/conversations/{id}/messages` — strict KB + multilingual SSE stream
- `GET /api/chat/home-suggestions` — random/manual home questions
- `GET /api/knowledge/export` — full KB JSON snapshot
- `GET|POST|PUT|DELETE /api/admin/general-questions` — non-KB Q&A routing
- `GET|PUT /api/admin/ai-config` — all chatbot tunables (incl. `multilingual` bool)

## Test Credentials
See `/app/memory/test_credentials.md`
