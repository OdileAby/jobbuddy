# JobBuddy

An AI-powered job application assistant. Paste your resume and a job description — JobBuddy scores the match, identifies skill gaps, rewrites your resume to better target the role, and drafts a tailored cover letter.

**Live demo:** https://jobbuddy-2i6k.onrender.com/
![JobBuddy screenshot](screenshot.png)
*(Free hosting — first load after inactivity takes ~30-60 seconds to wake up.)*

## Features

- **Match analysis** — a 0-100 score with reasoning, matching skills, missing skills, and concrete improvement suggestions, returned as structured JSON and rendered as a visual scorecard
- **PDF resume upload** — extracts text from PDF resumes, with graceful handling of scanned/image-only files
- **Resume tailoring** — rewrites the resume to naturally surface job-relevant keywords, then re-scores it to show the before → after improvement
- **Cover letter generation** — a 250-350 word letter grounded in the actual resume
- **PDF export** — download the tailored resume and cover letter as formatted PDFs
- **Abuse protection** — per-IP rate limiting and input size caps on all LLM-backed endpoints

## Architecture
Browser (vanilla JS + CSS)
│
▼
FastAPI backend ──► Claude API (analysis, tailoring, cover letters)
│
├──► pypdf (resume text extraction)
└──► reportlab (PDF generation)

A single FastAPI app serves both the static frontend and the API. Deployed on Render from this repository.

## Design decisions

**Honesty over score inflation.** The resume tailoring prompt is explicitly forbidden from inventing skills or experience. Keywords are only added where the original resume shows genuine supporting evidence; requirements the candidate doesn't meet are surfaced separately as `honest_gaps` rather than fabricated. Stuffing a resume with false keywords would raise the score and betray the user.

**Structured outputs with defensive parsing.** Analysis endpoints instruct the model to return strict JSON. Because LLMs occasionally wrap output in markdown fences or return malformed JSON, all model output passes through a parsing layer that strips fences and converts parse failures into clean HTTP errors instead of crashes.

**Re-scoring through the same pipeline.** The tailored resume's new score comes from running it back through the identical analysis prompt used for the original — an honest before/after comparison rather than asking the model to grade its own rewrite in the same call.

**Cost protection in depth.** Per-IP rate limits (via slowapi) and input length caps (via Pydantic validation) limit spend from any single user; a prepaid API budget with auto-reload disabled caps worst-case total spend at the account level.

## Known limitations

- Tailored resumes preserve the structure and content of the original but not the visual design of the source PDF (formatting is lost at text extraction)
- Match scores vary a few points between runs on identical input — an inherent property of LLM non-determinism (an evaluation suite is the planned next step)
- Scanned image-only PDFs are detected and rejected rather than OCR'd

## Running locally

A single FastAPI app serves both the static frontend and the API. Deployed on Render from this repository.

## Design decisions

**Honesty over score inflation.** The resume tailoring prompt is explicitly forbidden from inventing skills or experience. Keywords are only added where the original resume shows genuine supporting evidence; requirements the candidate doesn't meet are surfaced separately as `honest_gaps` rather than fabricated. Stuffing a resume with false keywords would raise the score and betray the user.

**Structured outputs with defensive parsing.** Analysis endpoints instruct the model to return strict JSON. Because LLMs occasionally wrap output in markdown fences or return malformed JSON, all model output passes through a parsing layer that strips fences and converts parse failures into clean HTTP errors instead of crashes.

**Re-scoring through the same pipeline.** The tailored resume's new score comes from running it back through the identical analysis prompt used for the original — an honest before/after comparison rather than asking the model to grade its own rewrite in the same call.

**Cost protection in depth.** Per-IP rate limits (via slowapi) and input length caps (via Pydantic validation) limit spend from any single user; a prepaid API budget with auto-reload disabled caps worst-case total spend at the account level.

## Known limitations

- Tailored resumes preserve the structure and content of the original but not the visual design of the source PDF (formatting is lost at text extraction)
- Match scores vary a few points between runs on identical input — an inherent property of LLM non-determinism (an evaluation suite is the planned next step)
- Scanned image-only PDFs are detected and rejected rather than OCR'd



## Stack

FastAPI · Anthropic Claude API · pypdf · reportlab · slowapi · vanilla HTML/CSS/JS · Render