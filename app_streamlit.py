import streamlit as st
import pandas as pd
import time
from models import QuestionBank, HistoryStore
from engine import SpacedRepetitionEngine

st.set_page_config(page_title="DocQuiz Web", layout="centered")

EXCEL_PATH = "https://raw.githubusercontent.com/onomatorHanze/didactic-octo-spork/main/data/quizvragen.xlsx"

# --------------------------------------------------------
# Cache Excel loading
# --------------------------------------------------------
@st.cache_data(ttl=60)
def get_vakken(path):
    xls = pd.ExcelFile(path, engine="openpyxl")
    return xls.sheet_names

@st.cache_data(ttl=60)
def load_questions_from_excel(path, sheet_name):
    df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    return df.to_dict(orient="records")


# --------------------------------------------------------
# UI: Startscherm
# --------------------------------------------------------
st.title("📘 DocQuiz Web")
st.markdown("Oefen je kennis per vak via een slimme quiz.")

vakken = get_vakken(EXCEL_PATH)
vak = st.selectbox("Kies een vak/tabblad:", vakken)
num_questions = st.number_input("Aantal vragen:", 1, 20, 5)

if st.button("Start quiz"):
    vragen = load_questions_from_excel(EXCEL_PATH, vak)
    
    st.session_state["vragen"] = vragen[:num_questions]
    st.session_state["vak"] = vak
    st.session_state["index"] = 0
    st.session_state["score"] = {"correct": 0, "wrong": 0}
    st.rerun()

if st.button("🔄 Vernieuw quizdata"):
    st.cache_data.clear()
    st.success("Data vernieuwd! Nieuwe vragen worden geladen...")
    time.sleep(1)
    st.rerun()


# --------------------------------------------------------
# QUIZ LOGICA
# --------------------------------------------------------
if "vragen" in st.session_state and st.session_state["vragen"]:
    qs = st.session_state["vragen"]
    i = st.session_state["index"]

    if i >= len(qs):
        st.balloons()
        st.write("🎉 **Klaar!**")
        st.metric("✅ Goed", st.session_state["score"]["correct"])
        st.metric("❌ Fout", st.session_state["score"]["wrong"])
        st.stop()

    q = qs[i]

    st.progress((i + 1) / len(qs))
    st.subheader(f"({st.session_state['vak']}) Vraag {i+1}: {q['text']}")

    # --------------------------------------------------------
    # AFBEELDING TONEN
    # --------------------------------------------------------
    if "image_path" in q and isinstance(q["image_path"], str) and q["image_path"].strip() != "":
        image_path = "data/" + q["image_path"]
        try:
            st.image(image_path, use_column_width=True)
        except:
            st.warning(f"Afbeelding niet gevonden: {image_path}")

    # --------------------------------------------------------
    # FORMULE (LATEX) TONEN
    # --------------------------------------------------------
    if "formula_latex" in q and isinstance(q["formula_latex"], str):
        if q["formula_latex"].strip() != "":
            st.latex(q["formula_latex"])

    # --------------------------------------------------------
    # ANTWOORDVERWERKING
    # --------------------------------------------------------
    antwoord = None

    # MEERKEUZE
    if q["type"] == "mc":
        opties = eval(q["choices"])
        antwoord = st.radio("Kies het juiste antwoord:", opties, index=None)
        correct = opties[int(q["answer"])]

    # TRUE/FALSE
    elif q["type"] == "tf":
        opties = ["Waar", "Onwaar"]
        antwoord = st.radio("Waar of Onwaar?", opties, index=None)
        correct = "Waar" if q["answer"] else "Onwaar"

    # INPUT
    elif q["type"] == "input":
        antwoord = st.text_input("Jouw antwoord:")
        correct = str(q["answer"])

        if st.button("Controleer"):
            if antwoord.strip() == correct.strip():
                st.success("✅ Goed!")
                st.session_state["score"]["correct"] += 1
            else:
                st.error(f"❌ Fout! Correct was: **{correct}**")
                st.session_state["score"]["wrong"] += 1
            time.sleep(1.5)
            st.session_state["index"] += 1
            st.rerun()
        st.stop()

    # AUTOMATISCH CONTROLEREN VOOR MC EN TF
    if antwoord is not None:
        if antwoord == correct:
            st.success("✅ Goed!")
            st.session_state["score"]["correct"] += 1
        else:
            st.error(f"❌ Fout! Correct was: **{correct}**")
            st.session_state["score"]["wrong"] += 1

        time.sleep(1.5)
        st.session_state["index"] += 1
        st.rerun()
