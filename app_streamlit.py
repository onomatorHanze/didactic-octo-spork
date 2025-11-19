import streamlit as st
import requests
import time

st.set_page_config(page_title="DocQuiz Web", layout="centered")

# JSON met vragen
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
    questions = questions_all[: int(num_questions)]

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

    # Afbeelding
    safe_show_image(q.get("image_url", ""))

    qtype = q.get("type")
    correct_raw = q.get("answer")

    # ----------------------------
    # Meerkeuze
    # ----------------------------
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
            if answer_idx == int(correct_raw):
                st.success("✅ Goed!")
                st.session_state["score"]["correct"] += 1
            else:
                st.error(f"❌ Fout! Correct was: {choices[int(correct_raw)]}")
                st.session_state["score"]["wrong"] += 1

            time.sleep(1)
            st.session_state["index"] += 1
            st.rerun()

    # ----------------------------
    # Waar / Onwaar
    # ----------------------------
    elif qtype == "tf":
        user_choice = st.radio("Waar of onwaar?", ["Waar", "Onwaar"], key=f"tf_{i}")
        correct = "Waar" if bool(correct_raw) else "Onwaar"

        if st.button("Controleer", key=f"tf_check_{i}"):
            if user_choice == correct:
                st.success("✅ Goed!")
                st.session_state["score"]["correct"] += 1
            else:
                st.error(f"❌ Fout! Correct was: {correct}")
                st.session_state["score"]["wrong"] += 1

            time.sleep(1)
            st.session_state["index"] += 1
            st.rerun()

    # ----------------------------
    # Input-vraag
    # ----------------------------
    else:
        user_input = st.text_input("Je antwoord:", key=f"inp_{i}")
        correct = str(correct_raw)

        if st.button("Controleer", key=f"inp_check_{i}"):
            if user_input.strip() == correct.strip():
                st.success("✅ Goed!")
                st.session_state["score"]["correct"] += 1
            else:
                st.error(f"❌ Fout! Correct was: {correct}")
                st.session_state["score"]["wrong"] += 1

            time.sleep(1)
            st.session_state["index"] += 1
            st.rerun()
