async function analyze() {
    const resume = document.getElementById("resume").value.trim();
    const jd = document.getElementById("jd").value.trim();
    const btn = document.getElementById("analyzeBtn");
    const errorBox = document.getElementById("errorBox");
    const results = document.getElementById("results");

    errorBox.style.display = "none";
    results.style.display = "none";

    if (!resume || !jd) {
        errorBox.textContent = "Please fill in both fields.";
        errorBox.style.display = "block";
        return;
    }

    btn.disabled = true;
    btn.textContent = "Analyzing...";

    try {
        const response = await fetch("/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ resume: resume, job_description: jd }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Something went wrong.");
        }

        const data = await response.json();
        renderResults(data);
    } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
    } finally {
        btn.disabled = false;
        btn.textContent = "Analyze match";
    }
}

function renderResults(data) {
    const circle = document.getElementById("scoreCircle");
    circle.textContent = data.match_score + "%";
    window.lastScore = data.match_score;
    circle.style.background =
        data.match_score >= 70 ? "#34c77b" :
            data.match_score >= 45 ? "#e8a33d" : "#f26d6d";
    circle.style.color = "#0f1117";
    document.getElementById("scoreReasoning").textContent = data.score_reasoning;

    document.getElementById("matchingSkills").innerHTML = data.matching_skills
        .map(s => `<span class="tag match">${escapeHtml(s)}</span>`).join("");

    document.getElementById("missingSkills").innerHTML = data.missing_skills
        .map(s => `<span class="tag miss">${escapeHtml(s)}</span>`).join("");

    document.getElementById("suggestions").innerHTML = data.suggestions
        .map(s => `
        <div class="suggestion">
          <div class="issue">${escapeHtml(s.issue)}</div>
          <div class="fix">${escapeHtml(s.fix)}</div>
        </div>`).join("");

    document.getElementById("results").style.display = "block";
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
async function uploadPdf() {
    const input = document.getElementById("pdfInput");
    const status = document.getElementById("uploadStatus");
    const file = input.files[0];

    if (!file) return;

    status.className = "";
    status.textContent = "Extracting text...";

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/upload-resume", {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Upload failed.");
        }

        const data = await response.json();
        document.getElementById("resume").value = data.text;
        status.className = "ok";
        status.textContent = "✓ Text extracted — review it above.";
    } catch (err) {
        status.className = "err";
        status.textContent = err.message;
    } finally {
        input.value = "";
    }
}
async function generateCoverLetter() {
    const resume = document.getElementById("resume").value.trim();
    const jd = document.getElementById("jd").value.trim();
    const btn = document.getElementById("coverBtn");
    const errorBox = document.getElementById("errorBox");

    btn.disabled = true;
    btn.textContent = "Writing...";

    try {
        const response = await fetch("/cover-letter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ resume: resume, job_description: jd }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Something went wrong.");
        }

        const data = await response.json();
        document.getElementById("coverText").textContent = data.cover_letter;
        document.getElementById("coverCard").style.display = "block";
    } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
    } finally {
        btn.disabled = false;
        btn.textContent = "Generate cover letter";
    }
}

function copyCoverLetter() {
    const text = document.getElementById("coverText").textContent;
    navigator.clipboard.writeText(text);
}
async function tailorResume() {
    const resume = document.getElementById("resume").value.trim();
    const jd = document.getElementById("jd").value.trim();
    const btn = document.getElementById("tailorBtn");
    const errorBox = document.getElementById("errorBox");

    btn.disabled = true;
    btn.textContent = "Tailoring (takes ~30s)...";

    try {
        const response = await fetch("/tailor-resume", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ resume: resume, job_description: jd }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Something went wrong.");
        }

        const data = await response.json();

        document.getElementById("oldScorePill").textContent =
            (window.lastScore ?? "–") + "%";
        document.getElementById("newScorePill").textContent = data.new_score + "%";
        document.getElementById("newScoreReasoning").textContent = data.new_score_reasoning;

        document.getElementById("changesList").innerHTML = data.changes_made
            .map(c => `<li>${escapeHtml(c)}</li>`).join("");

        document.getElementById("keywordsAdded").innerHTML = data.keywords_added
            .map(k => `<span class="tag match">${escapeHtml(k)}</span>`).join("");

        document.getElementById("honestGaps").innerHTML = data.honest_gaps
            .map(g => `<span class="tag miss">${escapeHtml(g)}</span>`).join("");

        document.getElementById("tailoredText").textContent = data.tailored_resume;
        document.getElementById("tailorCard").style.display = "block";
    } catch (err) {
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
    } finally {
        btn.disabled = false;
        btn.textContent = "Tailor my resume";
    }
}

async function downloadPdf(text, filename, btn) {
    const originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Preparing PDF...";

    try {
        const response = await fetch("/download-pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: text, filename: filename }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "PDF generation failed.");
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename + ".pdf";
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        const errorBox = document.getElementById("errorBox");
        errorBox.textContent = err.message;
        errorBox.style.display = "block";
    } finally {
        btn.disabled = false;
        btn.textContent = originalLabel;
    }
}

function downloadResume() {
    const text = document.getElementById("tailoredText").textContent;
    downloadPdf(text, "tailored-resume", event.target);
}

function downloadCoverLetter() {
    const text = document.getElementById("coverText").textContent;
    downloadPdf(text, "cover-letter", event.target);
}