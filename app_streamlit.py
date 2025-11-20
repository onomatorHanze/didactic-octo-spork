import streamlit as st
import requests
import time
from datetime import datetime
from models import HistoryStore
import random

st.set_page_config(page_title="DocQuiz Web", layout="centered")

# ---------------------------------------------------------
# JSON met vragen
# ---------------------------------------------------------
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
# SLIMME SELECTIE (Spaced Repetition + Leitner)
# ---------------------------------------------------------
def smart_select_questions(questions, history: HistoryStore, n=5):
    """Selecteer vragen via spaced repetition + Leitner boxes."""

    BOX_WAIT = {
        0: 0,                  # direct opnieuw
        1: 5 * 60,             # 5 minuten
        2: 15 * 60,            # 15 minuten
        3: 60 * 60,            # 1 uur
        4: 24 * 60 * 60,       # 1 dag
        5: 3 * 24 * 60 * 60    # 3 dagen
    }

    now = datetime.now()
    candidates = []

    for q in questions:
        qid = q.get("id")
        h = history.data["history"].get(qid, None)

        if h:
            box = h.get("box", 0)
            last = h.get("last")
            if last:
                last_dt = datetime.fromisoformat(last)
                delta = (now - last_dt).total_seconds()
            else:
                delta = 999999999
        else:
            box = 0
            delta = 999999999

        # ❌ Wachttijd niet verstreken → blokkeer vraag
        if delta < BOX_WAIT[box]:
            continue

        # ✔ Prioriteit: slechter beheerde vragen eerder
        days_ago = delta / 86400
        priority = (5 - box) * 3 + days_ago

        candidates.append((priority, q))

    # Als er te weinig kandidaten zijn → vul aan met willekeur
    if len(candidates) < n:
        rest = [q for q in questions if q not in [qq for _, qq in candidates]]
        random.shuffle(rest)
        while len(candidates) < n and rest:
            candidates.append((0, rest.pop()))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [q for _, q in candidates[:n]]


# ---------------------------------------------------------
# STARTSCHERM
# ---------------------------------------------------------
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
    history = HistoryStore("data/user_history.json")

    # ✔ Slim algoritme kiezen
    questions = smart_select_questions(
        questions_all,
        history,
        int(num_questions)
    )

    st.session_state["questions"] = questions
    st.session_state["vak"] = vak
    st.session_state["index"] = 0
    st.session_state["score"] = {"correct": 0, "wrong": 0}
    st.rerun()


# ---------------------------------------------------------
# QUIZ
# ---------------------------------------------------------
if "questions" in st.session_state and st.session_state["questions"]:

    qs = st.session_state["questions"]
    i = st.session_state["index"]

    # EINDE
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

            HistoryStore("data/user_history.json").update_question(q["id"], correct)

            time.sleep(1)
            st.session_state["index"] += 1
            st.rerun()

    # ---------------------------------------------------------
    # WAAR/ONWAAR
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

            HistoryStore("data/user_history.json").update_question(q["id"], is_correct)

            time.sleep(1)
            st.session_state["index"] += 1
            st.rerun()
