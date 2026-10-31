# Technical Approach Report: Skill-Gap and Job-Match Engine

This report explains how the demo in this repository works, which models and tools it uses, and how it could grow into a real Cynbit feature.

---

## 1. What the app does

The user uploads a resume and chooses a target role. The app then shows:
1. the skills found in the resume,
2. a match score for the role,
3. the missing skills,
4. training modules that cover those missing skills,
5. an optional short learning plan.

## 2. How it works

```
Resume (PDF or TXT)
  -> read the text (pypdf)
  -> AI extracts skills as JSON (Gemini)
  -> clean up skill names
  -> user checks and edits the skills
  -> compare with the role's required skills -> score and gaps
  -> rank training modules by how many gaps they cover
  -> optional learning plan (Gemini)
```

Everything is in one Streamlit file (`app.py`). Each step is its own small function, so any step can be tested or replaced without touching the others.

## 3. Data

| File | What it contains | Where it came from |
|------|------------------|--------------------|
| `data/modules.json` | 9 sample training modules with level, duration and skills | Written by me for this demo |
| `data/roles.json` | 5 sample job roles with required skills | Written by me for this demo |
| Resume | PDF or TXT file | Uploaded by the user |

Cynbit's real course list and role definitions are not public, so the two data files are examples. In a real version they would come from BitElevate's course data and Cynbit Studio's job listings.

**Privacy:** the app reads the resume in memory and does not save it. The text is sent to the Gemini API to extract skills. A real version would need user consent and a data policy.

## 4. Model choices

| Task | What I used | Why |
|------|-------------|-----|
| Find skills in a resume | Gemini (a fast, low-cost model) | Good at pulling structured information from text, and has a free tier for testing |
| Compare skills with a role | Exact match after cleaning names | Simple and easy to explain |
| Compare skills (next step) | Text embeddings | Would give partial credit for related skills such as Flask and FastAPI |
| Write the learning plan | Gemini | Short text where small differences are fine |

**Why no model training?** There is no labelled data yet, and a ready-made AI model already does this task well. Training a custom model only makes sense later, if testing shows steady mistakes.

The model name can be changed with the `GEMINI_MODEL` setting, without editing the code.

## 5. Prompt design

**Skill extraction prompt**
- Asks for JSON only, in the form `{"skills": [...]}`.
- Asks for short, lowercase skill names with no duplicates.
- Tells the AI to include only skills the resume actually supports, so it does not make things up.
- Uses only the first 8,000 characters of the resume to keep cost and time low.
- Uses temperature 0, so the same resume gives the same result.

**Learning plan prompt**
- Gives the AI only the role, the score, the missing skills and the module names.
- Asks for 3 to 4 encouraging sentences and says not to invent facts.
- The AI never sees the resume itself, so it cannot repeat personal details.

## 6. Cleaning and matching

- **Cleaning:** lowercase the text, remove extra spaces, and map common variants to one name (for example `ReactJS` and `react.js` become `react`, and `sklearn` becomes `scikit-learn`).
- **Score:** matched skills divided by required skills, times 100.
- **Recommendations:** each module is ranked by how many of the user's missing skills it covers. The top 3 are shown, with the exact skills each one covers.

This is easy to explain. A user can see exactly why a module was suggested.

## 7. Human in the loop

Before the score is calculated, the extracted skills appear in an editable box. The user can delete wrong skills or add missing ones, and the score updates right away. This is the main protection against AI mistakes, and it matches the human-in-the-loop approach Cynbit describes on its blog.

## 8. How to test it properly

The demo has not been formally tested yet. This is the plan:

1. Collect about 50 resumes (with consent, or made-up ones) and list their skills by hand.
2. Check **precision** (how many found skills are correct) and **recall** (how many real skills were found).
3. Track how often users edit the AI's list.
4. Compare exact matching with embedding matching.
5. Test for fairness: use resumes that are identical except for name, gender or college, and confirm the score does not change.

## 9. Limitations

- It uses sample data, so results are only as good as those files.
- Exact matching misses similar skills that are not in the alias list.
- Scanned PDFs with no text cannot be read (there is no OCR).
- Every required skill counts the same. There is no "must-have" and "nice-to-have" split yet.
- A resume only lists claimed skills. Cynbit Studio practice results could later prove them.
- There are no automated tests yet.

## 10. Four-week plan

| Week | What to do | Result |
|------|-----------|--------|
| 1 | Replace sample data with real course and role data. Label a set of resumes for testing. | Real data and a test set |
| 2 | Add embedding-based matching and must-have vs nice-to-have skills. Add automated tests. | Better matching and tests |
| 3 | Move the logic into a backend API (FastAPI), save results with consent, and bring in Cynbit Studio practice data as proof of skill. | Backend API |
| 4 | Run a pilot with a small group of learners, measure the results and decide whether to continue. | Pilot results |

## 11. Practical notes

- **API keys:** stored in a `.env` file locally and in Streamlit Secrets when deployed. They are never uploaded to GitHub.
- **Cost:** one AI call per resume, plus one optional call for the plan. The 8,000-character limit keeps usage small.
- **Errors:** the app catches errors and shows a readable message instead of crashing.

## 12. How to run

```
pip install -r requirements.txt
# add GEMINI_API_KEY to a .env file
python -m streamlit run app.py
```

See `README.md` for the full setup steps and the live demo link.
