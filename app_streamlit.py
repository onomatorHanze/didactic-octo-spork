import streamlit as st
import pandas as pd
import time
import math
from models import QuestionBank, HistoryStore
from engine import SpacedRepetitionEngine

st.set_page_config(page_title="DocQuiz Web", layout="centered")

# ----------------------------
# Inladen van Excel-vakken
# ----------------------------
EXCEL_PATH = "https://raw.githubusercontent.com/onomatorHanze/didactic-octo-spork/main/data/quizvragen.xlsx"


@st.cache_data(ttl=60)
def get_vakken(path):
    """Lees de namen van de tabbladen (vakken) in."""
    xls = pd.ExcelFile(path, engine="openpyxl")
    return xls.sheet_names


@st.cache_data(ttl=60)
def load_questions_from_excel(path, sheet_name):
    """Laad een tabblad (vak) als JSON-conversie."""
    df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    questions = df.to_dict(orient="records")
    return {"meta": {"source": path, "sheet": sheet_name}, "questions": questions}


def _safe_str(val: object) -> str:
    """Zet NaN / None om naar lege string, anders naar gestripte string."""
    if val is None:
        return ""
    try:
        # pandas NaN
        if isinstance(val, float) and math.isnan(val):
            return ""
    except Exception:
        pass
    return str(val).strip()


def show_details(q: dict):
    """Toon uitleg en (optioneel) LaTeX-formule bij een vraag."""
    uitleg = _safe_str(q.get("explanation"))
    if uitleg:
        st.info(f"ℹ️ {uitleg}")

    formule = _safe_str(q.get("formula_latex"))
    if formule:
        # in Excel staat bv: I = \\frac{U}{R}
        st.latex(formule)


def get_image_url(q: dict) -> str | None:
    """
    Bepaal de te tonen afbeeldings-URL.
    - Eerst 'image_url' (volledige URL die admin.py schrijft)
    - Daarna 'image_path' (oude stijl, relatief pad in repo of al een url)
    """
    # 1) Nieuwe stijl: directe URL
    img_url = _safe_str(q.get("image_url"))
    if img_url:
        return img_url

    # 2) Oude stijl: image_path
    img_path = _safe_str(q.get("image_path"))
    if not img_path:
        return None

    # als het al een volledige URL is, gebruik die
    if img_path.startswith("http://") or img_path.startswith("https://"):
        return img_path

    # anders: behandel het als een pad in de repo
    # bijvoorbeeld: "assets/ohm_schema.png" of "data/images/..."
    base = "https://raw.githubusercontent.com/onomatorHanze/didactic-octo-spork/main/"
    return base + img_path


# ----------------------------
# Startscherm
# ----------------------------
vakken = get_vakken(EXCEL_PATH)
st.title("📘 DocQuiz Web")
st.markdown("Oefen je kennis per vak via een slimme quiz.")

vak = st.selectbox("Kies een vak/tabblad:", vakken)
num_questions = st.number_input("Aantal vragen:", 1, 20, 5)

if st.button("Start quiz"):
    qdata = load_questions_from_excel(EXCEL_PATH, vak)
    qbank = QuestionBank()  # optioneel
    history = HistoryStore()
    engine = SpacedRepetitionEngine(qbank, history)

    # hier zou je num_questions kunnen gebruiken om te sampelen,
    # maar voorlopig nemen we alle vragen
    st.session_state["questions"] = qdata["questions"]
    st.session_state["vak"] = vak
    st.session_state["index"] = 0
    st.session_state["score"] = {"correct": 0, "wrong": 0}
    st.rerun()

# ----------------------------
# Vernieuw-knop
# ----------------------------
if st.button("🔄 Vernieuw quizdata"):
    st.cache_data.clear()  # wist de cache
    st.success("Data vernieuwd! De nieuwste vragen worden geladen...")
    time.sleep(1)
    st.rerun()

# ----------------------------
# Quizgedeelte
# ----------------------------
if "questions" in st.session_state and st.session_state["questions"]:
    qs = st.session_state["questions"]
    i = st.session_state["index"]

    # Check einde quiz
    if i >= len(qs):
        st.balloons()
        st.write("🎉 **Klaar!**")
        st.metric("✅ Goed", st.session_state["score"]["correct"])
        st.metric("❌ Fout", st.session_state["score"]["wrong"])
        st.stop()

    q = qs[i]

    # Voortgang
    st.progress((i + 1) / len(qs))
    st.subheader(f"({st.session_state['vak']}) Vraag {i+1}: {q['text']}")

    # Afbeelding laten zien als die er is
    img_url = get_image_url(q)
    if img_url:
        st.image(img_url, width=400)

    antwoord = None  # veilige default

    # ---------------------------- Meerkeuzevraag
    if q["type"] == "mc":
        keuzes_lijst = []
        if isinstance(q.get("choices"), str) and q["choices"]:
            try:
                keuzes_lijst = eval(q["choices"])
            except Exception:
                keuzes_lijst = []

        keuzes = ["Maak een keuze..."] + keuzes_lijst
        antwoord = st.radio("Kies het juiste antwoord:", keuzes, index=0, key=f"q{i}")
        correct = keuzes_lijst[int(q["answer"])] if keuzes_lijst else None

    # ---------------------------- Waar/Onwaar vraag
    elif q["type"] == "tf":
        keuzes = ["Maak een keuze...", "Waar", "Onwaar"]
        antwoord = st.radio("Waar of Onwaar?", keuzes, index=0, key=f"q{i}")
        correct = "Waar" if q["answer"] else "Onwaar"

    # ---------------------------- Invoervraag
    elif q["type"] == "input":
        antwoord = st.text_input("Voer je antwoord in:", key=f"q{i}")
        correct = str(q["answer"])

        if st.button("Controleer antwoord"):
            goed = antwoord.strip() == correct.strip()
            if goed:
                st.success("✅ Goed!")
                st.session_state["score"]["correct"] += 1
            else:
                st.error(f"❌ Fout! Correct was: {correct}")
                st.session_state["score"]["wrong"] += 1

            # Uitleg + formule tonen
            show_details(q)

            time.sleep(1.5)
            st.session_state["index"] += 1
            st.rerun()

        st.stop()  # voorkomt dat code verder loopt

    # ---------------------------- Automatische controle (voor MC en TF)
    if antwoord and antwoord != "Maak een keuze...":
        goed = antwoord == correct
        if goed:
            st.success("✅ Goed!")
            st.session_state["score"]["correct"] += 1
        else:
            st.error(f"❌ Fout! Correct was: {correct}")
            st.session_state["score"]["wrong"] += 1

        # Uitleg + formule tonen
        show_details(q)

        time.sleep(1.5)
        st.session_state["index"] += 1
        st.rerun()
