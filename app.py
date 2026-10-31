import json
import os
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


def get_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


ALIASES = {
    "js": "javascript", "reactjs": "react", "react.js": "react",
    "nodejs": "node.js", "node": "node.js", "ml": "machine learning",
    "sklearn": "scikit-learn", "postgres": "postgresql",
    "large language models": "llm", "llms": "llm",
    "retrieval augmented generation": "rag", "restful api": "rest api",
    "rest apis": "rest api", "apis": "rest api", "api": "rest api",
    "amazon web services": "aws", "github": "git", "cicd": "ci/cd",
    "fast api": "fastapi", "py": "python",
}


def get_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        try:
            key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            key = None
    if not key:
        st.error(
            "GEMINI_API_KEY not found. Add it to your .env file (local) "
            "or Streamlit secrets (deployed)."
        )
        st.stop()
    return genai.Client(api_key=key.strip())


def normalize(skill: str) -> str:
    s = re.sub(r"\s+", " ", skill.lower().strip())
    return ALIASES.get(s, s)


def read_resume(uploaded) -> str:
    if uploaded.name.lower().endswith(".pdf"):
        reader = PdfReader(uploaded)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return uploaded.read().decode("utf-8", errors="ignore")


def extract_skills(client, text: str) -> list:
    prompt = (
        "Extract technical skills from this resume. Return ONLY JSON like "
        '{"skills": ["python", "sql"]}. Use short lowercase names, no duplicates, '
        "only skills explicitly supported by the text.\n\nRESUME:\n" + text[:8000]
    )
    resp = client.models.generate_content(
        model=get_model_name(),
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    data = json.loads(resp.text)
    return sorted({normalize(s) for s in data.get("skills", []) if isinstance(s, str)})


def match_role(candidate: list, required: list):
    cand = set(candidate)
    matched = [r for r in required if r in cand]
    missing = [r for r in required if r not in cand]
    score = round(100 * len(matched) / len(required)) if required else 0
    return score, matched, missing


def recommend_modules(missing: list, modules: list, top_n: int = 3):
    ranked = []
    for m in modules:
        covered = [s for s in m["skills"] if s in missing]
        if covered:
            ranked.append((len(covered), m, covered))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[:top_n]


def explain_plan(client, role, score, missing, recs) -> str:
    rec_text = ", ".join(m["name"] for _, m, _ in recs) or "none"
    prompt = (
        f"A learner is targeting the role '{role}' with a {score}% skill match. "
        f"Missing skills: {', '.join(missing) or 'none'}. "
        f"Recommended modules: {rec_text}. "
        "Write a short, encouraging 3-4 sentence learning plan. Do not invent facts."
    )
    resp = client.models.generate_content(
        model=get_model_name(),
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.4),
    )
    return resp.text


# ---------------- UI ----------------
st.set_page_config(page_title="Skill-Gap Engine", page_icon="🎯")
st.title("🎯 Skill-Gap & Job-Match Engine")
st.caption(
    "Proof of concept for Cynbit: connecting BitElevate training "
    "with Cynbit Studio job matching"
)

with open(BASE_DIR / "data" / "modules.json", encoding="utf-8") as f:
    MODULES = json.load(f)
with open(BASE_DIR / "data" / "roles.json", encoding="utf-8") as f:
    ROLES = json.load(f)

role = st.selectbox("Target role", list(ROLES.keys()))
uploaded = st.file_uploader("Upload resume (PDF or TXT)", type=["pdf", "txt"])

if uploaded and st.button("Analyze"):
    client = get_client()
    with st.spinner("Reading resume and extracting skills..."):
        try:
            text = read_resume(uploaded)
            if not text.strip():
                st.error("Could not read any text from this file (maybe a scanned PDF).")
                st.stop()
            st.session_state["skills"] = extract_skills(client, text)
            st.session_state.pop("plan", None)
        except Exception as e:
            st.error(f"Something went wrong: {e}")
            st.stop()

if "skills" in st.session_state:
    # Human-in-the-loop: user can correct the extracted skills
    edited = st.text_area(
        "Extracted skills (edit if wrong, comma separated)",
        ", ".join(st.session_state["skills"]),
    )
    skills = sorted({normalize(s) for s in edited.split(",") if s.strip()})

    score, matched, missing = match_role(skills, ROLES[role])
    st.metric("Role match", f"{score}%")
    st.progress(score / 100)

    c1, c2 = st.columns(2)
    c1.subheader("✅ You have")
    c1.write(", ".join(matched) or "None yet")
    c2.subheader("❌ Gaps")
    c2.write(", ".join(missing) or "No gaps!")

    recs = recommend_modules(missing, MODULES)
    st.subheader("📚 Recommended modules")
    for n, m, covered in recs:
        st.markdown(
            f"**{m['name']}** ({m['level']}, {m['weeks']} weeks) covers "
            f"{n} gap(s): {', '.join(covered)}"
        )
    if not recs:
        st.info("No catalog module covers your gaps.")

    if st.button("Generate learning plan"):
        client = get_client()
        with st.spinner("Writing your plan..."):
            try:
                st.session_state["plan"] = explain_plan(client, role, score, missing, recs)
            except Exception as e:
                st.error(f"Something went wrong: {e}")

    if "plan" in st.session_state:
        st.subheader("🗺️ Learning plan")
        st.write(st.session_state["plan"])