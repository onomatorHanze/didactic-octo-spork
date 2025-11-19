import streamlit as st
import json
import requests
import base64
import time
import math
import uuid

# -------------------------------------------------------------
# CONFIG – via Streamlit Secrets
# -------------------------------------------------------------
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
JSON_PATH = st.secrets["FILE_PATH"]     # bv "data/questions.json"
IMAGE_DIR = "data/images"

JSON_RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{JSON_PATH}"
JSON_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{JSON_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# -------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------
def clean(v):
    """Zorgt dat None / NaN lege strings worden."""
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return v


def github_get(url):
    return requests.get(url, headers={"Authorization": f"token {TOKEN}"})


def github_put(url, content_bytes, sha, message):
    encoded = base64.b64encode(content_bytes).decode()
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha

    return requests.put(
        url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )


# -------------------------------------------------------------
# SAFE IMAGE
# -------------------------------------------------------------
def safe_image(url: str):
    if not url or not isinstance(url, str):
        st.caption("Geen afbeelding.")
        return
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            st.image(r.content, width=350)
        else:
            st.caption("⚠️ Afbeelding niet geladen.")
    except:
        st.caption("⚠️ Fout bij afbeelding.")


# -------------------------------------------------------------
# LOAD DATA (GEEN CACHE!)
# -------------------------------------------------------------
def load_data():
    r = github_get(JSON_RAW_URL)
    if r.status_code != 200:
        st.error(f"Kon JSON niet laden ({r.status_code}).")
        st.stop()

    try:
        data = r.json()
    except:
        st.error("JSON is ongeldig op GitHub.")
        st.stop()

    fixed = {}
    for tab, qs in data.items():
        fixed[tab] = qs if isinstance(qs, list) else []
    return fixed


# -------------------------------------------------------------
# SAVE JSON + force reload
# -------------------------------------------------------------
def save_json(data):
    cleaned = {}
    for tab, questions in data.items():
        cleaned[tab] = [{k: clean(v) for k, v in q.items()} for q in questions]

    raw = json.dumps(cleaned, indent=2, ensure_ascii=False).encode("utf-8")

    meta = github_get(JSON_API_URL).json()
    sha = meta.get("sha")

    r = github_put(JSON_API_URL, raw, sha, "Update questions.json via Admin")

    if r.status_code not in (200, 201):
        st.error(f"❌ Opslaan mislukt (status {r.status_code})")
        return False

    # BELANGRIJK!
    st.cache_data.clear()

    return True


# -------------------------------------------------------------
# IMAGE UPLOADEN
# -------------------------------------------------------------
def upload_image(file_bytes, filename):
    path = f"{IMAGE_DIR}/{filename}"
    api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"

    meta = github_get(api_url).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode()
    payload = {"message": f"Upload {filename}", "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(api_url, headers={"Authorization": f"token {TOKEN}"}, data=json.dumps(payload))

    if r.status_code not in (200, 201):
        st.error("❌ Upload mislukt")
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{path}"


# -------------------------------------------------------------
# SESSION STATE
# -------------------------------------------------------------
if "edit_vak" not in st.session_state:
    st.session_state["edit_vak"] = None
if "edit_index" not in st.session_state:
    st.session_state["edit_index"] = None
if "del_vak" not in st.session_state:
    st.session_state["del_vak"] = None
if "del_index" not in st.session_state:
    st.session_state["del_index"] = None


# -------------------------------------------------------------
# MAIN DATA
# -------------------------------------------------------------
data = load_data()

st.subheader("📘 Kies een vak")
current_vak = st.selectbox("Vak:", list(data.keys()))
questions = data[current_vak]


# -------------------------------------------------------------
# OVERZICHT
# -------------------------------------------------------------
st.subheader("📄 Overzicht vragen")

for i, q in enumerate(questions):
    col1, col2, col3, col4 = st.columns([6, 1, 1, 1])

    with col1:
        text = q.get("text", "")
        st.write(f"**{i}: {text[:80]}{'…' if len(text)>80 else ''}**")

    with col2:
        if q.get("image_url"):
            st.caption("🖼")

    with col3:
        if st.button("✏️", key=f"edit_{current_vak}_{i}"):
            st.session_state["edit_vak"] = current_vak
            st.session_state["edit_index"] = i
            st.session_state["del_vak"] = None
            st.session_state["del_index"] = None
            st.rerun()

    with col4:
        if st.button("❌", key=f"del_{current_vak}_{i}"):
            st.session_state["del_vak"] = current_vak
            st.session_state["del_index"] = i
            st.session_state["edit_vak"] = None
            st.session_state["edit_index"] = None
            st.rerun()


# -------------------------------------------------------------
# VERWIJDEREN
# -------------------------------------------------------------
if st.session_state["del_vak"] is not None:
    dv = st.session_state["del_vak"]
    di = st.session_state["del_index"]

    q = data[dv][di]

    st.markdown("---")
    st.subheader("❓ Vraag verwijderen?")
    st.write(q.get("text", ""))

    c1, c2 = st.columns(2)

    with c1:
        if st.button("✔ Verwijderen"):
            data[dv].pop(di)
            if save_json(data):
                st.success("Verwijderd!")
                st.session_state["del_vak"] = None
                st.session_state["del_index"] = None
                st.rerun()

    with c2:
        if st.button("✖ Annuleren"):
            st.session_state["del_vak"] = None
            st.session_state["del_index"] = None
            st.rerun()


# -------------------------------------------------------------
# BEWERKEN
# -------------------------------------------------------------
if st.session_state["edit_vak"] is not None:
    ev = st.session_state["edit_vak"]
    ei = st.session_state["edit_index"]
    q = data[ev][ei]

    st.markdown("---")
    st.subheader(f"✏ Vraag bewerken")

    new_text = st.text_input("Vraagtekst", q.get("text", ""))
    new_topic = st.text_input("Topic", q.get("topic", ""))
    new_expl = st.text_area("Uitleg", q.get("explanation", ""))

    type_options = ["mc", "tf", "input"]
    new_type = st.selectbox("Type", type_options, index=type_options.index(q.get("type", "mc")))

    if new_type == "mc":
        opts_str = ", ".join(q.get("choices", []))
        new_opts = st.text_input("Opties (komma gescheiden)", opts_str)
        new_ans = st.number_input("Juiste index", 0, value=int(q.get("answer", 0)))
    elif new_type == "tf":
        new_opts = ""
        new_ans = st.selectbox("Correct?", [True, False], index=0 if q.get("answer") else 1)
    else:
        new_opts = ""
        new_ans = st.text_input("Correct antwoord", str(q.get("answer", "")))

    st.markdown("### Afbeelding")
    safe_image(q.get("image_url", ""))
    up_img = st.file_uploader("Nieuwe afbeelding", type=["jpg", "jpeg", "png"])
    remove_img = st.checkbox("Verwijder huidige afbeelding")

    if st.button("💾 Opslaan"):
        q["text"] = clean(new_text)
        q["topic"] = clean(new_topic)
        q["explanation"] = clean(new_expl)
        q["type"] = new_type

        if new_type == "mc":
            q["choices"] = [s.strip() for s in new_opts.split(",") if s.strip()]
        else:
            q["choices"] = []

        q["answer"] = new_ans

        if remove_img:
            q["image_url"] = ""
        elif up_img:
            ext = up_img.name.split(".")[-1]
            fname = f"{ev}_{uuid.uuid4().hex[:6]}.{ext}"
            url = upload_image(up_img.read(), fname)
            if url:
                q["image_url"] = url

        if save_json(data):
            st.success("Opgeslagen!")
            st.session_state["edit_vak"] = None
            st.session_state["edit_index"] = None
            st.rerun()


# -------------------------------------------------------------
# NIEUWE VRAAG
# -------------------------------------------------------------
st.markdown("---")
st.subheader("➕ Nieuwe vraag")

text = st.text_input("Vraagtekst")
qtype = st.selectbox("Type", ["mc", "tf", "input"])
topic = st.text_input("Topic")
expl = st.text_area("Uitleg")

if qtype == "mc":
    opts = st.text_input("Opties (komma gescheiden)")
    ans = st.number_input("Juiste index", 0)
elif qtype == "tf":
    opts = ""
    ans = st.selectbox("Correct?", [True, False])
else:
    opts = ""
    ans = st.text_input("Correct antwoord")

img = st.file_uploader("Afbeelding", type=["jpg", "jpeg", "png"])

if st.button("Toevoegen"):
    new_img_url = ""
    if img:
        ext = img.name.split(".")[-1]
        fname = f"{current_vak}_{uuid.uuid4().hex[:6]}.{ext}"
        url = upload_image(img.read(), fname)
        if url:
            new_img_url = url

    new_q = {
        "id": f"q{uuid.uuid4().hex[:6]}",
        "text": clean(text),
        "topic": clean(topic),
        "explanation": clean(expl),
        "type": qtype,
        "choices": [s.strip() for s in opts.split(",")] if qtype == "mc" else [],
        "answer": ans,
        "image_url": new_img_url
    }

    data[current_vak].append(new_q)

    if save_json(data):
        st.success("Toegevoegd!")
        st.rerun()
