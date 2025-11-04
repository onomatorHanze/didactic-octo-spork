import streamlit as st
import pandas as pd
from models import QuestionBank, HistoryStore
from engine import SpacedRepetitionEngine

st.set_page_config(page_title="DocQuiz Web", layout="centered")

# ----------------------------
# Inladen van Excel-vakken
# ----------------------------
EXCEL_PATH = "data/quizvragen.xlsx"

@st.cache_data
def get_vakken(path):
    """Lees de namen van de tabbladen (vakken) in."""
    xls = pd.ExcelFile(path)
    return xls.sheet_names

@st.cache_data
def load_questions_from_excel(path, sheet_name):
    """Laad een tabblad (vak) als JSON-conversie."""
    df = pd.read_excel(path, sheet_name=sheet_name)
    # Simpele controle: kolomnamen aanpassen indien nodig
    questions = df.to_dict(orient="records")
    return {"meta": {"source": path, "sheet": sheet_name}, "questions": questions}

# ----------------------------
# Basisdata
# ----------------------------
vakken = get_vakken(EXCEL_PATH)
st.title("📘 DocQuiz Web")
st.markdown("Oefen je kennis per vak via een slimme quiz.")

vak = st.selectbox("Kies een vak/tabblad:", vakken)
num_questions = st.number_input("Aantal vragen:", 1, 20, 5)

if st.button("Start quiz"):
    qdata = load_questions_from_excel(EXCEL_PATH, vak)
    qbank = QuestionBank()  # optioneel voor consistentie
    history = HistoryStore()
    engine = SpacedRepetitionEngine(qbank, history)

    st.session_state["questions"] = qdata["questions"]
    st.session_state["vak"] = vak
    st.session_state["index"] = 0
    st.session_state["score"] = {"correct": 0, "wrong": 0}
    st.rerun()

# ----------------------------
# Quizgedeelte
# ----------------------------
if "questions" in st.session_state and st.session_state["questions"]:
    qs = st.session_state["questions"]
    i = st.session_state["index"]
    q = qs[i]

    st.subheader(f"({st.session_state['vak']}) Vraag {i+1}: {q['text']}")
    answer = None
    correct = None

    if q["type"] == "mc":
        answer = st.radio("Kies het juiste antwoord:", eval(q["choices"]))
        correct = eval(q["choices"])[int(q["answer"])]
    elif q["type"] == "tf":
        answer = st.radio("Waar of Onwaar?", ["Waar", "Onwaar"])
        correct = "Waar" if q["answer"] == True else "Onwaar"
    elif q["type"] == "input":
        answer = st.text_input("Voer je antwoord in:")
        correct = str(q["answer"])

    if st.button("Controleer antwoord"):
        goed = answer == correct
        if goed:
            st.success("✅ Goed!")
            st.session_state["score"]["correct"] += 1
        else:
            st.error(f"❌ Fout! Correct was: {correct}")
            st.session_state["score"]["wrong"] += 1

        st.session_state["index"] += 1
        if st.session_state["index"] < len(qs):
            st.button("Volgende vraag", on_click=st.rerun)
        else:
            st.balloons()
            st.write("🎉 **Klaar!**")
            st.metric("Goed", st.session_state["score"]["correct"])
            st.metric("Fout", st.session_state["score"]["wrong"])
