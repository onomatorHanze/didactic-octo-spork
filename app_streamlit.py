import streamlit as st
import requests
import time
from datetime import datetime
from models import HistoryStore   # ✔ gebruikt jouw models.py
import random

st.set_page_config(page_title="DocQuiz Web", layout="centered")

# JSON met vragen (GitHub versie)
JSON_URL = "https://raw.githubusercontent.com/onomatorHanze/didactic-octo-spork/main/data/questions.json"

@st.cache_data(ttl=60)
def load_data():
    r = requests.get(JSON_URL, timeout=5)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else {}

def safe_show_image(url: str):
    if not isinstance(url, str) or not url.strip():
        return
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            st.image(r.content, use_column_width=True)
    except:
        pass

# ---------------------------------------------------------
# SLIM SELECTIE-ALGORITME  (Leitner box + tijd sinds oefening)
# ---------------------------------------------------------
def smart_select_questions(questions, history: HistoryStore, n=5):
    enriched = []
    now = datetime.now()

    for q in questions:
        qid = q.get("id")
        hist = history.data["history"].get(qid, None)

        if hist:
            box = hist.get("box", 0)
            last = hist.get("last")
            if last:
                last_dt = datetime.fromisoformat(last)
                days_ago = (now - last_dt).days
            else:
                days_ago = 999
        else:
            box = 0
            days_ago = 999

        # prioriteit berekening
        priority = (5 - box) * 3 + days_ago / 5
        enriched.append((priority, q))

    # Sorteren op prioriteit
    enriched.sort(key=lambda x: x[0], reverse=True)

    return [q for _, q in enriched[:n]]

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

    # ✔ SLIM ALGORITME HIER
    history = HistoryStore("data/user_history.json")
    questions = smart_select_questions(questions_all, history, int(num_questions))

    st.session_state["questions"] = questions
    st.session_state["vak"] = vak
    st.session_state["index"] = 0
    st.session_state["score"] = {"correct": 0, "wrong": 0}
    st.rerun()

# ----------------------------
# Quiz
# ----------------------------
if "questions" in st.session_state and st.session_state["questions"]:
    qs = st.session_state["questions"]
    i = st.session_state["index"]

    # EINDE?
    if i >= len(qs):
        st.balloons()
        st.success("🎉 **Klaar!**")
        st.metric("Goed", st.session_state["score"]["correct"])
        st.metric("Fout", st.session_state["score"]["wrong"])
        st.stop()

    q = qs[i]
    st.progress((i + 1) / len(qs))
    st.subheader(f"({st.session_state['vak']}) Vraag {i+1}")
    st.write(q.get("text", ""))

    safe_show_image(q.get("image_url", ""))

    qtype = q.get("type")
    correct_raw = q.get("answer")

    # ---------------------------------------------------------
    # MEERKEUZE
    # ---------------------------------------------------------
    if qtype == "mc":
        choices = q.get("choices", [])
        if not isinstance(choices, list):
            choices = []

        answer_idx = st.radio(
            "Kies het juiste antwoord:",
            list(range(len(choices))),
            format_func=lambda idx: choices[idx],
            key=f"mc_{i}",
        )

        if st.button("Controleer", key=f"mc_check_{i}"):

            correct = answer_idx == int(correct_raw)

            if correct:
                st.success("✅ Goed!")
                st.session_state["score"]["correct"] += 1
            else:
                st.error(f"❌ Fout! Correct was: {choices[int(correct_raw)]}")
                st.session_state["score"]["wrong"] += 1

            # ✔ UPDATE HISTORYSTORE
            HistoryStore("data/user_history.json").update_question(q["id"], correct)

            time.sleep(1)
            st.session_state["index"] += 1
            st.rerun()

    # ---------------------------------------------------------
    # WAAR / ONWAAR
    # ---------------------------------------------------------
    elif qtype == "tf":
        user_choice = st.radio("Waar of onwaar?", ["Waar", "Onwaar"], key=f"tf_{i}")
        correct = "Waar" if bool(correct_raw) else "Onwaar"

        if st.button("Controleer", key=f"tf_check_{i}"):
            is_correct = user_choice == correct

            if is_correct:
                st.success("✅ Goed!")
                st.session_state["score"]["correct"] += 1
            else:
                st.error(f"❌ Fout! Correct was: {correct}")
                st.session_state["score"]["wrong"] += 1

            # ✔ UPDATE HISTORYSTORE
            HistoryStore("data/user_history.json").update_question(q["id"], is_correct)

            time.sleep(1)
            st.session_state["index"] += 1
            st.rerun()

    # ---------------------------------------------------------
    # INPUT-VRAAG
    # ---------------------------------------------------------
    else:
        user_input = st.text_input("Je antwoord:", key=f"inp_{i}")
        correct = str(correct_raw)

        if st.button("Controleer", key=f"inp_check_{i}"):

            is_correct = user_input.strip() == correct.strip()

            if is_correct:
                st.success("✅ Goed!")
                st.session_state["score"]["correct"] += 1
            else:
                st.error(f"❌ Fout! Correct was: {correct}")
                st.session_state["score"]["wrong"] += 1

            # ✔ UPDATE HISTORYSTORE
            HistoryStore("data/user_history.json").update_question(q["id"], is_correct)

            time.sleep(1)
            st.session_state["index"] += 1
            st.rerun()
