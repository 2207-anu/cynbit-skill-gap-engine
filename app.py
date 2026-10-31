import json
import os
import re

import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from pypdf import PdfReader

load_dotenv()
MODEL = "llama-3.3-70b-versatile"

ALIASES = {
    "js": "javascript", "reactjs": "react", "react.js": "react",
    "nodejs": "node.js", "node": "node.js", "ml": "machine learning",
    "sklearn": "scikit-learn", "postgres": "postgresql",
    "large language models": "llm", "llms": "llm",
    "retrieval augmented generation": "rag", "restful api": "rest api",
    "rest apis": "rest api", "apis": "rest api", "amazon web services": "aws",
    "github": "git", "cicd": "ci/cd",
}


def get_client():
    key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", None)
    if not key:
        st.error("GROQ_API_KEY not found. Add it to .env or Streamlit secrets.")
        st.stop()
    return Groq(api_key=key)


def normalize(skill: str) -> str:
    s = re.sub(r"\s+", " ", skill.lower().strip())
    return ALIASES.get(s, s)


def read_resume(uploaded) -> str:
    if uploaded.name.lower().endswith(".pdf"):
        reader = PdfReader(uploaded)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return uploaded.read().decode("utf-8", errors="ignore")


def extract_skills(client, text: str) -> list[str]:
    prompt = (
        "Extract technical skills from this resume. Return ONLY JSON like "
        '{"skills": ["python", "sql"]}. Use short lowercase names, no duplicates, '
        "only skills explicitly supported by the text.\n\nRESUME:\n" + text[:8000]
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    data = json.loads(resp.choices[0].message.content)
    return sorted({normalize(s) for s in data.get("skills", [])})


def match_role(candidate: list[str], required: list[str]):
    cand = set(candidate)
    matched = [r for r in required if r in cand]
    missing = [r for r in required if r not in cand]
    score = round(100 * len(matched) / len(required)) if required else 0
    return score, matched, missing


def recommend_modules(missing: list[str], modules: list[dict], top_n: int = 3):
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
        f"Missing skills: {', '.join(missing) or 'none'}. Recommended modules: {rec_text}. "
        "Write a short, encouraging 3-4 sentence learning plan. Do not invent facts."
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content


st.set_page_config(page_title="Skill-Gap Engine", page_icon="🎯")
st.title("🎯 Skill-Gap & Job-Match Engine")
st.caption("Proof of concept for Cynbit: BitElevate training x Cynbit Studio job matching")

with open("data/modules.json", encoding="utf-8") as f:
    MODULES = json.load(f)
with open("data/roles.json", encoding="utf-8") as f:
    ROLES = json.load(f)

role = st.selectbox("Target role", list(ROLES.keys()))
uploaded = st.file_uploader("Upload resume (PDF or TXT)", type=["pdf", "txt"])

if uploaded and st.button("Analyze"):
    client = get_client()
    with st.spinner("Reading resume and extracting skills..."):
        text = read_resume(uploaded)
        skills = extract_skills(client, text)

    # Human-in-the-loop: let the user correct extracted skills
    st.session_state["skills"] = skills

if "skills" in st.session_state:
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
        st.write(explain_plan(client, role, score, missing, recs))