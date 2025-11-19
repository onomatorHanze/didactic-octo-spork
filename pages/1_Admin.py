import streamlit as st
import json
import requests
import base64
import time
import math
import uuid

# -------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
JSON_PATH = st.secrets["FILE_PATH"]           # data/questions.json
IMAGE_DIR = "data/images"

JSON_RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{JSON_PATH}"
JSON_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{JSON_PATH}"

# -------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------
def clean(v):
    """Zorgt dat geen enkele NaN of None in JSON terecht komt."""
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return v

def github_get(path):
    r = requests.get(path, headers={"Authorization": f"token {TOKEN}"})
    return r

def github_put(path, content_bytes, sha, message):
    encoded = base64.b64encode(content_bytes).decode()
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(
        path,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload)
    )
    return r


# -------------------------------------------------------------
# LOAD QUESTIONS.JSON
# -------------------------------------------------------------
@st.cache_data
def load_json():
    r = github_get(JSON_RAW_URL)
    if r.status_code != 200:
        st.error("Kan JSON niet laden van GitHub!")
        st.stop()

    data = r.json()
    return data


# -------------------------------------------------------------
# SAVE QUESTIONS.JSON
# -------------------------------------------------------------
def save_json(data):
    """Schrijft JSON terug naar GitHub."""

    # 1. CLEAN ALL VALUES
    cleaned = {}
    for tab, questions in data.items():
        cleaned[tab] = []
        for q in questions:
            q2 = {k: clean(v) for k, v in q.items()}
            cleaned[tab].append(q2)

    # 2. BYTES
    raw = json.dumps(cleaned, indent=2).encode()

    # 3. SHA ophalen
    meta = github_get(JSON_API_URL).json()
    sha = meta.get("sha")

    # 4. Uploaden
    r = github_put(JSON_API_URL, raw, sha, "Update questions.json via Admin")

    return r.status_code in (200, 201)


# -------------------------------------------------------------
# IMAGE UPLOAD
# -------------------------------------------------------------
def upload_image(file_bytes, filename):
    path = f"{IMAGE_DIR}/{filename}"
    api = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"

    meta = github_get(api).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode()
    payload = {"message": f"Upload image {filename}", "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(api,
                     headers={"Authorization": f"token {TOKEN}"},
                     data=json.dumps(payload))

    if r.status_code not in (200, 201):
        st.error("❌ Afbeelding upload mislukt")
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{path}"


# -------------------------------------------------------------
# SAFE IMAGE PREVIEW
# -------------------------------------------------------------
def safe_image(url):
    if not url or not isinstance(url, str) or url.strip() == "":
        st.caption("Geen afbeelding.")
        return
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            st.image(r.content, width=350)
        else:
            st.caption("⚠️ Afbeelding kon niet worden geladen.")
    except:
        st.caption("⚠️ Afbeelding fout.")


# -------------------------------------------------------------
# PAGE UI
# -------------------------------------------------------------
st.set_page_config(page_title="Admin", layout="centered")
st.title("🔧 DocQuiz Admin")

data = load_json()

# TABS = vakken zoals "DC", "AC", "Wiskunde 3"
vak = st.selectbox("Vak:", list(data.keys()))
questions = data[vak]

st.subheader("📄 Overzicht vragen")

# -------------------------------------------------------------
# LIST QUESTIONS
# -------------------------------------------------------------
for i, q in enumerate(questions):
    col1, col2, col3 = st.columns([6,1,1])

    with col1:
        st.write(f"**{i}: {q['text'][:60]}{'…' if len(q['text'])>60 else ''}**")

    with col2:
        if q.get("image_url"):
            st.caption("🖼")

    with col3:
        if st.button("✏️", key=f"edit_{vak}_{i}"):
            st.session_state["edit"] = (vak, i)
            st.rerun()
        if st.button("❌", key=f"del_{vak}_{i}"):
            st.session_state["delete"] = (vak, i)
            st.rerun()


# -------------------------------------------------------------
# DELETE QUESTION
# -------------------------------------------------------------
if "delete" in st.session_state:
    dvak, di = st.session_state["delete"]
    st.markdown("---")
    st.error(f"Vraag verwijderen?\n\n**{questions[di]['text']}**")
    c1, c2 = st.columns(2)

    with c1:
        if st.button("✔ Verwijderen"):
            questions.pop(di)
            if save_json(data):
                st.success("Verwijderd!")
                st.session_state.pop("delete")
                st.rerun()

    with c2:
        if st.button("✖ Annuleren"):
            st.session_state.pop("delete")
            st.rerun()


# -------------------------------------------------------------
# EDIT QUESTION
# -------------------------------------------------------------
if "edit" in st.session_state:
    evak, ei = st.session_state["edit"]
    q = questions[ei]

    st.markdown("---")
    st.subheader("Vraag bewerken")

    new_text = st.text_input("Vraagtekst", q["text"])
    new_type = st.selectbox("Type", ["mc","tf","input"], index=["mc","tf","input"].index(q["type"]))

    new_topic = st.text_input("Topic", clean(q.get("topic")))
    new_expl = st.text_area("Uitleg", clean(q.get("explanation")))

    # type-specific
    if new_type == "mc":
        opts = ", ".join(q.get("choices", []))
        new_opts = st.text_input("Opties (komma gescheiden)", opts)
        new_ans = st.number_input("Juiste antwoord index", min_value=0, value=int(q["answer"]))
    elif new_type == "tf":
        new_opts = ""
        new_ans = st.selectbox("Correct?", [True, False], index=0 if q["answer"] else 1)
    else:
        new_opts = ""
        new_ans = st.text_input("Correct antwoord", clean(q["answer"]))

    st.markdown("### Afbeelding")
    safe_image(q.get("image_url"))

    img_file = st.file_uploader("Nieuwe afbeelding")
    remove_img = st.checkbox("Afbeelding verwijderen")

    if st.button("💾 Opslaan"):
        q["text"] = new_text
        q["type"] = new_type
        q["topic"] = new_topic
        q["explanation"] = new_expl
        q["choices"] = [s.strip() for s in new_opts.split(",")] if new_type=="mc" else []
        q["answer"] = new_ans

        if remove_img:
            q["image_url"] = ""
        elif img_file:
            ext = img_file.name.split(".")[-1].lower()
            fname = f"{vak}_{uuid.uuid4().hex[:6]}.{ext}"
            url = upload_image(img_file.read(), fname)
            if url:
                q["image_url"] = url

        if save_json(data):
            st.success("Opgeslagen!")
            st.session_state.pop("edit")
            st.rerun()

    if st.button("Annuleer"):
        st.session_state.pop("edit")
        st.rerun()


# -------------------------------------------------------------
# ADD QUESTION
# -------------------------------------------------------------
st.markdown("---")
st.subheader("➕ Nieuwe vraag toevoegen")

qt_text = st.text_input("Vraagtekst")
qt_type = st.selectbox("Type", ["mc","tf","input"])
qt_topic = st.text_input("Topic")
qt_expl = st.text_area("Uitleg")

if qt_type == "mc":
    qt_opts = st.text_input("Opties (komma gescheiden)")
    qt_ans = st.number_input("Juiste index", min_value=0, value=0)
elif qt_type == "tf":
    qt_opts = ""
    qt_ans = st.selectbox("Correct?", [True, False])
else:
    qt_opts = ""
    qt_ans = st.text_input("Antwoord")

qt_img = st.file_uploader("Afbeelding")

if st.button("Toevoegen"):

    new_q = {
        "id": f"q{uuid.uuid4().hex[:6]}",
        "text": clean(qt_text),
        "type": qt_type,
        "topic": clean(qt_topic),
        "explanation": clean(qt_expl),
        "choices": [s.strip() for s in qt_opts.split(",")] if qt_type=="mc" else [],
        "answer": qt_ans,
        "image_url": "",
    }

    if qt_img:
        ext = qt_img.name.split(".")[-1].lower()
        fname = f"{vak}_{uuid.uuid4().hex[:6]}.{ext}"
        url = upload_image(qt_img.read(), fname)
        if url:
            new_q["image_url"] = url

    questions.append(new_q)

    if save_json(data):
        st.success("Nieuwe vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
