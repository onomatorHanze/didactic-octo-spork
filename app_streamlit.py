import streamlit as st
import requests
import time
from models import QuestionBank, HistoryStore
from engine import SpacedRepetitionEngine

st.set_page_config(page_title="DocQuiz Web", layout="centered")

# Publieke JSON met alle vragen
JSON_URL = "https://raw.githubusercontent.com/onomatorHanze/didactic-octo-spork/main/data/questions.json"


@st.cache_data(ttl=60)
def load_data():
    r = requests.get(JSON_URL, timeout=5)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        data = {}
    return data


def safe_show_image(url: str):
    if not isinstance(url, str) or not url.strip():
        return
    try:
        r = requests.get(url, timeout=4)
        if r.status_code != 200:
            return
        st.image(r.content, use_column_width=True)
    except Exception:
        return


# ----------------------------
# Startscherm
# ----------------------------
data = load_data()
vakken = sorted(data.keys())

st.title("📘 DocQuiz Web")
st.markdown("Oefen je kennis per vak via een slimme quiz.")

if not vakken:
    st.warning("Er zijn nog geen vakken in de vragen-JSON.")
    st.stop()

vak = st.selectbox("Kies een vak:", vakken)
num_questions = st.number_input("Aantal vragen:", 1, 50, 5)

if st.button("Start quiz"):
    questions_all = data.get(vak, [])
    # Pak de eerste n (je kunt later random/spaced maken)
    questions = questions_all[: int(num_questions)]

    qbank = QuestionBank()
    history = HistoryStore()
    engine = SpacedRepetitionEngine(qbank, history)  # nu nog niet echt gebruikt

    st.session_state["questions"] = questions
    st.session_state["vak"] = vak
    st.session_state["index"] = 0
    st.session_state["score"] = {"correct": 0, "wrong": 0}
    st.experimental_rerun()

# Handmatige refresh-knop
if st.button("🔄 Vernieuw quizdata"):
    st.cache_data.clear()
    st.success("Data vernieuwd!")
    time.sleep(1)
    st.experimental_rerun()

# ----------------------------
# Quiz
# ----------------------------
if "questions" in st.session_state and st.session_state["questions"]:
    qs = st.session_state["questions"]
    i = st.session_state["index"]

    if i >= len(qs):
        st.balloons()
        st.write("🎉 **Klaar!**")
        st.metric("✅ Goed", st.session_state["score"]["correct"])
        st.metric("❌ Fout", st.session_state["score"]["wrong"])
        st.stop()

    q = qs[i]

    st.progress((i + 1) / len(qs))
    st.subheader(f"({st.session_state['vak']}) Vraag {i+1}")
    st.write(q.get("text", ""))

    # Afbeelding (indien aanwezig)
    img_url = q.get("image_url", "")
    safe_show_image(img_url)

    answer = None

    # Meerkeuze
    if q.get("type") == "mc":
        choices = q.get("choices", [])
        if not isinstance(choices, list):
            choices = []
        opties = ["Maak een keuze..."] + [str(c) for c in choices]
        answer = st.radio(
            "Kies het juiste antwoord:",
            opties,
            index=0,
            key=f"mc_{i}",
        )
        correct_idx = int(q.get("answer", 0))
        correct = str(choices[correct_idx]) if 0 <= correct_idx < len(choices) else ""

    # Waar / Onwaar
    elif q.get("type") == "tf":
        opties = ["Maak een keuze...", "Waar", "Onwaar"]
        answer = st.radio(
            "Waar of onwaar?",
            opties,
            index=0,
            key=f"tf_{i}",
        )
        correct = "Waar" if bool(q.get("answer", True)) else "Onwaar"

    # Invoervraag
    else:
        user_input = st.text_input("Je antwoord:", key=f"inp_{i}")
        correct = str(q.get("answer", ""))

        if st.button("Controleer antwoord", key=f"check_{i}"):
            goed = user_input.strip() == correct.strip()
            if goed:
                st.success("✅ Goed!")
                st.session_state["score"]["correct"] += 1
            else:
                st.error(f"❌ Fout! Correct was: {correct}")
                st.session_state["score"]["wrong"] += 1

            time.sleep(1.5)
            st.session_state["index"] += 1
            st.experimental_rerun()

        st.stop()

    # Automatische controle voor MC / TF
    if answer and answer != "Maak een keuze...":
        goed = (answer == correct)
        if goed:
            st.success("✅ Goed!")
            st.session_state["score"]["correct"] += 1
        else:
            st.error(f"❌ Fout! Correct was: {correct}")
            st.session_state["score"]["wrong"] += 1

        time.sleep(1.5)
        st.session_state["index"] += 1
        st.experimental_rerun()
