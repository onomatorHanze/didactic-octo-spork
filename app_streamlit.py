import streamlit as st
import pandas as pd
import time
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

    # Toon vraag en beantwoord automatisch
    if q["type"] == "mc":
        keuzes = ["Maak een keuze..."] + eval(q["choices"])
        antwoord = st.radio("Kies het juiste antwoord:", keuzes, index=0, key=f"q{i}")
        correct = eval(q["choices"])[int(q["answer"])]

    if antwoord != "Maak een keuze...":
        goed = antwoord == correct
        if goed:
            st.success("✅ Goed!")
            st.session_state["score"]["correct"] += 1
        else:
            st.error(f"❌ Fout! Correct was: {correct}")
            st.session_state["score"]["wrong"] += 1

        time.sleep(1.5)
        st.session_state["index"] += 1
        st.rerun()

    elif q["type"] == "tf":
        keuzes = ["Maak een keuze...", "Waar", "Onwaar"]
        antwoord = st.radio("Waar of Onwaar?", keuzes, index=0, key=f"q{i}")
        correct = "Waar" if q["answer"] == True else "Onwaar"

        if antwoord != "Maak een keuze...":
            goed = antwoord == correct
            if goed:
                    st.success("✅ Goed!")
                    st.session_state["score"]["correct"] += 1
            else:
                    st.error(f"❌ Fout! Correct was: {correct}")
                    st.session_state["score"]["wrong"] += 1

            time.sleep(1.5)
            st.session_state["index"] += 1
            st.rerun()


    elif q["type"] == "tf":
        antwoord = st.radio("Waar of Onwaar?", ["Waar", "Onwaar"], key=f"q{i}")
        correct = "Waar" if q["answer"] == True else "Onwaar"

        if antwoord:
            goed = antwoord == correct
            if goed:
                st.success("✅ Goed!")
                st.session_state["score"]["correct"] += 1
            else:
                st.error(f"❌ Fout! Correct was: {correct}")
                st.session_state["score"]["wrong"] += 1

            st.session_state["index"] += 1
            st.experimental_rerun()

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
            st.session_state["index"] += 1
            st.experimental_rerun()

    # Eindresultaat
    if st.session_state["index"] >= len(qs):
        st.balloons()
        st.write("🎉 **Klaar!**")
        st.metric("Goed", st.session_state["score"]["correct"])
        st.metric("Fout", st.session_state["score"]["wrong"])
        st.stop()
