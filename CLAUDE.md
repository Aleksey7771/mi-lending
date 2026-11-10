# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Landing page for a freelancer/small agency offering website development, mobile apps, and AI agents for SMB business clients. The goal is lead generation (contact form submissions) from business owners.

## Project Status

Pre-development phase. `research.md` contains the full research brief:
- **Section 1:** Design references and competitor analysis (Awwwards examples)
- **Section 2:** Ideal 7-block landing page structure for B2B
- **Section 3:** 2026 web design trends to apply
- **Expert audit section:** UX, conversion marketing, and client-perspective reviews

## Key Design Decisions (from research)

- **Stack direction:** Static HTML/CSS + vanilla JS or a lightweight framework. GSAP for hero animations, CSS `animation-timeline` for scroll-driven effects (no heavy JS libraries).
- **Typography:** One variable sans-serif font (Inter Variable, Manrope, or Plus Jakarta Sans), fluid sizing via `clamp()`.
- **Colors:** Dark navy + icy blue base, one warm accent for CTAs. Use `oklch()` and CSS custom properties.
- **No:** parallax, cursor effects, autoplay video with sound, entry pop-ups, stock "AI brain" imagery.

## Landing Page Structure (7 blocks in order)

1. **Hero** — offer + main CTA ("Получить расчёт") + secondary CTA ("Смотреть кейсы")
2. **Trust bar** — logos, certificates, key stats
3. **Catalog teaser** — 3 service directions with business outcomes (not tech stack)
4. **Pricing** — "от Х ₽" ranges, what's included, monthly costs
5. **Process** — 4–5 steps with timelines
6. **Cases + Reviews** — with metrics, real names, industry context
7. **Form + FAQ** — max 3–4 fields, Telegram/WhatsApp alternative, "what happens next"

## Conversion Rules

- Every CTA button text must state the outcome, not the action: "Получить расчёт за 24 часа" not "Отправить заявку".
- AI agents section must explain via use case ("отвечает в Telegram ночью") not technology ("LLM + RAG").
- Price transparency is non-negotiable: even a range prevents the visitor from assuming "too expensive".
- Form submit must show next steps immediately (response time + Telegram link).
