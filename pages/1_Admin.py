import streamlit as st
import json
import requests
import base64
import time
import uuid
import math

# -------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
JSON_PATH = st.secrets["FILE_PATH"]         # bijv. data/questions.json
IMAGE_DIR = "data/images"

RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{JSON_PATH}"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{JSON_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Vragenbeheer")


# -------------------------------------------------------------
# Helper functies
# -------------------------------------------------------------
def clean(val):
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    return val


def github_get(url):
    return requests.get(url, headers={"Authorization": f"token {TOKEN}"})


def github_put(url, bytes_content, sha, message):
    encoded = base64.b64encode(bytes_content).decode()
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha

    return requests.put(url,
                        headers={"Authorization": f"token {TOKEN}"},
                        data=json.dumps(payload))


def load_json():
    """Laadt ALTIJD verse JSON uit GitHub; nooit cache."""
    r = github_get(RAW_URL)
    if r.status_code != 200:
        st.error(f"JSON kon niet worden geladen (HTTP {r.status_code})")
        st.stop()

    try:
        data = r.json()
    except:
        st.error("Fout bij parsen van JSON")
        st.stop()

    fixed = {}
    for tab, qs in data.items():
        fixed[tab] = qs if isinstance(qs, list) else []

    return fixed


def save_json(data):
    """Slaat JSON op via GitHub API."""
    cleaned = {}

    for tab, questions in data.items():
        cl = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            q2 = {k: clean(v) for k, v in q.items()}
            cl.append(q2)
        cleaned[tab] = cl

    raw_bytes = json.dumps(cleaned, indent=2, ensure_ascii=False).encode("utf-8")

    meta = github_get(API_URL).json()
    sha = meta.get("sha")

    r = github_put(API_URL, raw_bytes, sha, "Update questions.json via Admin")

    if r.status_code not in (200, 201):
        st.error("❌ Opslaan mislukt!")
        try:
            st.json(r.json())
        except:
            pass
        return False

    return True


def upload_image(file_bytes, filename):
    """Upload afbeelding naar GitHub en return raw-url."""
    path = f"{IMAGE_DIR}/{filename}"
    api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"

    meta = github_get(api_url).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode()
    payload = {"message": f"Upload image {filename}", "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(api_url,
                      headers={"Authorization": f"token {TOKEN}"},
                      data=json.dumps(payload))

    if r.status_code not in (200, 201):
        st.error("❌ Fout bij uploaden afbeelding")
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{path}"


def safe_image(url):
    if not isinstance(url, str) or not url.strip():
        return
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            st.image(r.content, width=350)
    except:
        pass


# -------------------------------------------------------------
# Session state init
# -------------------------------------------------------------
for key in ["edit_vak", "edit_index", "del_vak", "del_index"]:
    if key not in st.session_state:
        st.session_state[key] = None


# -------------------------------------------------------------
# Data laden
# -------------------------------------------------------------
data = load_json()

st.subheader("📘 Kies een vak")
current_vak = st.selectbox("Vak:", list(data.keys()), key="vak_select")
questions = data[current_vak]


# -------------------------------------------------------------
# Overzicht vragen
# -------------------------------------------------------------
st.subheader("📄 Overzicht vragen")

for i, q in enumerate(questions):
    col1, col2, col3, col4 = st.columns([6, 1, 1, 1])

    with col1:
        short = q.get("text", "")[:80]
        st.write(f"**{i}: {short}**")

    with col2:
        if q.get("image_url"):
            st.caption("🖼")

    with col3:
        if st.button("✏️", key=f"edit_btn_{current_vak}_{i}"):
            st.session_state["edit_vak"] = current_vak
            st.session_state["edit_index"] = i
            st.session_state["del_vak"] = None
            st.session_state["del_index"] = None
            st.rerun()

    with col4:
        if st.button("❌", key=f"del_btn_{current_vak}_{i}"):
            st.session_state["del_vak"] = current_vak
            st.session_state["del_index"] = i
            st.session_state["edit_vak"] = None
            st.session_state["edit_index"] = None
            st.rerun()


# -------------------------------------------------------------
# Delete
# -------------------------------------------------------------
if st.session_state["del_vak"] is not None:
    dv = st.session_state["del_vak"]
    di = st.session_state["del_index"]

    st.markdown("---")
    st.warning(f"Vraag verwijderen?\n\n**{data[dv][di]['text']}**")
    c1, c2 = st.columns(2)

    with c1:
        if st.button("✔ Verwijderen", key="confirm_delete"):
            data[dv].pop(di)
            if save_json(data):
                st.success("Vraag verwijderd.")
                st.session_state["del_vak"] = None
                st.session_state["del_index"] = None
                time.sleep(1)
                st.rerun()

    with c2:
        if st.button("✖ Annuleren", key="cancel_delete"):
            st.session_state["del_vak"] = None
            st.session_state["del_index"] = None
            st.rerun()


# -------------------------------------------------------------
# Edit
# -------------------------------------------------------------
if st.session_state["edit_vak"] is not None:
    ev = st.session_state["edit_vak"]
    ei = st.session_state["edit_index"]
    q = data[ev][ei]

    st.markdown("---")
    st.subheader(f"Vraag bewerken – {ev} #{ei}")

    new_text = st.text_input("Vraagtekst", q.get("text", ""), key=f"edit_text_{ei}")

    type_options = ["mc", "tf", "input"]
    new_type = st.selectbox("Type", type_options,
                            index=type_options.index(q.get("type", "mc")),
                            key=f"edit_type_{ei}")

    new_topic = st.text_input("Topic", q.get("topic", ""), key=f"edit_topic_{ei}")
    new_expl = st.text_area("Uitleg", q.get("explanation", ""), key=f"edit_expl_{ei}")

    # Type specifiek
    if new_type == "mc":
        opts = q.get("choices", [])
        opts_str = ", ".join(opts)
        new_opts_str = st.text_input("Opties (komma gescheiden)", opts_str,
                                     key=f"edit_opts_{ei}")
        new_ans = st.number_input("Juiste index", min_value=0,
                                  value=int(q.get("answer", 0)),
                                  key=f"edit_ans_{ei}")
    elif new_type == "tf":
        new_opts_str = ""
        new_ans = st.selectbox("Correct?", [True, False],
                               index=0 if q.get("answer", True) else 1,
                               key=f"edit_tf_{ei}")
    else:
        new_opts_str = ""
        new_ans = st.text_input("Juiste antwoord", q.get("answer", ""),
                                key=f"edit_anstr_{ei}")

    # Afbeelding
    st.markdown("### Afbeelding")
    safe_image(q.get("image_url", ""))

    new_img = st.file_uploader("Nieuwe afbeelding", type=["png", "jpg", "jpeg"],
                               key=f"edit_img_{ei}")
    remove_img = st.checkbox("Afbeelding verwijderen",
                             key=f"edit_remove_{ei}")

    # Opslaan
    if st.button("💾 Opslaan", key=f"edit_save_{ei}"):

        q["text"] = clean(new_text)
        q["type"] = new_type
        q["topic"] = clean(new_topic)
        q["explanation"] = clean(new_expl)

        if new_type == "mc":
            q["choices"] = [s.strip() for s in new_opts_str.split(",") if s.strip()]
        else:
            q["choices"] = []

        q["answer"] = new_ans

        if remove_img:
            q["image_url"] = ""
        elif new_img:
            ext = new_img.name.split(".")[-1].lower()
            fname = f"{ev}_{uuid.uuid4().hex[:6]}.{ext}"
            url = upload_image(new_img.read(), fname)
            if url:
                q["image_url"] = url

        if save_json(data):
            st.success("Opgeslagen!")
            st.session_state["edit_vak"] = None
            st.session_state["edit_index"] = None
            time.sleep(1)
            st.rerun()

    if st.button("Annuleer", key=f"edit_cancel_{ei}"):
        st.session_state["edit_vak"] = None
        st.session_state["edit_index"] = None
        st.rerun()


# -------------------------------------------------------------
# Nieuwe vraag
# -------------------------------------------------------------
st.markdown("---")
st.subheader("➕ Nieuwe vraag toevoegen")

new_t = st.text_input("Vraagtekst", key="new_t")
new_ty = st.selectbox("Type", ["mc", "tf", "input"], key="new_ty")
new_top = st.text_input("Topic", key="new_top")
new_ex = st.text_area("Uitleg", key="new_ex")

if new_ty == "mc":
    new_opts_str = st.text_input("Opties", key="new_opts")
    new_ans = st.number_input("Juiste index", min_value=0, value=0, key="new_ans")
elif new_ty == "tf":
    new_opts_str = ""
    new_ans = st.selectbox("Correct?", [True, False], key="new_ans_tf")
else:
    new_opts_str = ""
    new_ans = st.text_input("Juiste antwoord", key="new_ans_inp")

new_img = st.file_uploader("Afbeelding", type=["png", "jpg", "jpeg"],
                           key="new_imgfile")

if st.button("Toevoegen", key="new_add"):
    if not new_t.strip():
        st.error("Vraagtekst mag niet leeg zijn.")
    else:
        img_url = ""
        if new_img:
            ext = new_img.name.split(".")[-1].lower()
            fname = f"{current_vak}_{uuid.uuid4().hex[:6]}.{ext}"
            url = upload_image(new_img.read(), fname)
            if url:
                img_url = url

        opts = [s.strip() for s in new_opts_str.split(",") if s.strip()] if new_ty == "mc" else []

        q = {
            "id": f"q{uuid.uuid4().hex[:6]}",
            "text": clean(new_t),
            "type": new_ty,
            "topic": clean(new_top),
            "explanation": clean(new_ex),
            "choices": opts,
            "answer": new_ans,
            "image_url": img_url,
        }

        data[current_vak].append(q)

        if save_json(data):
            st.success("Vraag toegevoegd!")
            time.sleep(1)
            st.rerun()
