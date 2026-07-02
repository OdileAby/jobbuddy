import os
import json
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from anthropic import Anthropic
from pypdf import PdfReader
import io
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
load_dotenv()

app = FastAPI(title="Job Application Assistant")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


class AnalyzeRequest(BaseModel):
    resume: str = Field(max_length=15000)
    job_description: str = Field(max_length=15000)

class PdfRequest(BaseModel):
    text: str = Field(max_length=30000)
    filename: str = "document"

PROMPT_TEMPLATE = """You are a career advisor. Analyze how well this resume matches this job description.

<resume>
{resume}
</resume>

<job_description>
{job_description}
</job_description>

Respond with ONLY a valid JSON object, no other text, no markdown fences. Use exactly this structure:
{{
  "match_score": <integer 0-100>,
  "score_reasoning": "<2-3 sentence explanation of the score>",
  "matching_skills": ["<skill>", ...],
  "missing_skills": ["<skill>", ...],
  "suggestions": [
    {{"issue": "<what is weak or missing>", "fix": "<concrete action to take>"}},
    ...
  ]
}}

Include 2-4 suggestions. Be honest and specific — do not inflate the score."""


COVER_LETTER_TEMPLATE = """You are an expert career writer. Write a cover letter for this candidate applying to this job.

<resume>
{resume}
</resume>

<job_description>
{job_description}
</job_description>

Rules:
- 250-350 words, three or four paragraphs
- Professional but warm tone, no clichés like "I am writing to express my interest"
- Reference 2-3 specific things from the resume that match the job's needs
- Never invent skills, experience, or achievements that are not in the resume
- If the job posting names the company, address it; otherwise keep it generic
- Do not include placeholder brackets like [Company Name] — write around unknowns naturally

Respond with ONLY the cover letter text. No preamble, no explanations, no subject line."""


TAILOR_TEMPLATE = """You are an expert resume writer. Rewrite this resume to better match this job description.

<resume>
{resume}
</resume>

<job_description>
{job_description}
</job_description>

Strict rules:
- NEVER invent skills, tools, experience, jobs, or achievements not present in the original resume
- Rephrase and reorganize existing content to naturally include keywords from the job description ONLY where the underlying experience genuinely supports them
- Keep the same overall structure and section order as the original resume
- Keep roughly the same length as the original
- Improve weak phrasing: use strong action verbs and quantify where the original provides numbers
- Do not add placeholder text or notes to the candidate

Respond with ONLY a valid JSON object, no other text, no markdown fences:
{{
  "tailored_resume": "<the full rewritten resume as plain text, preserving line breaks>",
  "changes_made": ["<short description of each significant change>", ...],
  "keywords_added": ["<keyword from the job description now naturally included>", ...],
  "honest_gaps": ["<skill from the job description that could NOT be added because the resume shows no evidence of it>", ...]
}}"""


def parse_model_json(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502,
            detail="Model returned invalid JSON. Try again.",
        )


def run_analysis(resume: str, job_description: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": PROMPT_TEMPLATE.format(
                    resume=resume,
                    job_description=job_description,
                ),
            }
        ],
    )
    return parse_model_json(response.content[0].text)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
@limiter.limit("10/hour")
def analyze(request: Request, body: AnalyzeRequest):
    return run_analysis(body.resume, body.job_description)


@app.post("/upload-resume")
def upload_resume(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    try:
        reader = PdfReader(file.file)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this PDF.")

    pages_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)

    full_text = "\n".join(pages_text).strip()

    if not full_text:
        raise HTTPException(
            status_code=422,
            detail="No text found in this PDF. It may be a scanned image.",
        )

    return {"text": full_text}


@app.post("/cover-letter")
@limiter.limit("5/hour")
def cover_letter(request: Request, body: AnalyzeRequest):
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": COVER_LETTER_TEMPLATE.format(
                    resume=request.resume,
                    job_description=request.job_description,
                ),
            }
        ],
    )
    return {"cover_letter": response.content[0].text.strip()}


@app.post("/tailor-resume")
@limiter.limit("5/hour")
def tailor_resume(request: Request, body: AnalyzeRequest):
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=3000,
        messages=[
            {
                "role": "user",
                "content": TAILOR_TEMPLATE.format(
                    resume=request.resume,
                    job_description=request.job_description,
                ),
            }
        ],
    )

    tailor_result = parse_model_json(response.content[0].text)

    new_analysis = run_analysis(
        tailor_result["tailored_resume"],
        request.job_description,
    )

    return {
        "tailored_resume": tailor_result["tailored_resume"],
        "changes_made": tailor_result.get("changes_made", []),
        "keywords_added": tailor_result.get("keywords_added", []),
        "honest_gaps": tailor_result.get("honest_gaps", []),
        "new_score": new_analysis["match_score"],
        "new_score_reasoning": new_analysis["score_reasoning"],
    }

def build_pdf(text: str) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
    )

    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        spaceAfter=8,
    )

    story = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        safe = block.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe = safe.replace("\n", "<br/>")
        story.append(Paragraph(safe, body_style))
        story.append(Spacer(1, 4))

    doc.build(story)
    buffer.seek(0)
    return buffer


@app.post("/download-pdf")
@limiter.limit("20/hour")
def download_pdf(request: Request, body: PdfRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="No text to convert.")

    pdf_buffer = build_pdf(request.text)

    safe_name = "".join(
        c for c in request.filename if c.isalnum() or c in ("-", "_")
    ) or "document"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}.pdf"'
        },
    )
app.mount("/", StaticFiles(directory="static", html=True), name="static")