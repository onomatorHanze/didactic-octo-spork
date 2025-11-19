import streamlit as st
import json
import requests
import base64
import uuid
import time
import math


# -------------------------------------------------------------
# SETTINGS & GITHUB CONFIG
# -------------------------------------------------------------
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
JSON_PATH = st.secrets["FILE_PATH"]
IMAGE_DIR = "data/images"

RAW = (
    f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{JSON_PATH}"
)
API = (
    f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{JSON_PATH}"
)

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin")


# -------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------
def clean(v):
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return v


def github_get(url):
    return requests.get(url, headers={"Authorization": f"token {TOKEN}"})


def github_put(url, bytes, sha, msg):
    encoded = base64.b64encode(bytes).decode()
    payload = {"message": msg, "content": encoded}
    if sha:
        payload["sha"] = sha
    return requests.put(
        url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )


def safe_img(url):
    if not url:
        return
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            st.image(r.content, width=350)
    except:
        pass


# -------------------------------------------------------------
# LOAD JSON — always fresh
# -------------------------------------------------------------
# 🔧 BELANGRIJK: reload_key als parameter zodat Streamlit opnieuw uitvoert
def load_data(reload_key):
    url = f"{RAW}?ts={int(time.time())}"
    r = github_get(url)

    if r.status_code != 200:
        st.error("Kon JSON niet laden!")
        st.stop()

    try:
        data = r.json()
    except:
        st.error("JSON corrupt!")
        st.stop()

    fixed = {}
    for tab, qs in data.items():
        fixed[tab] = qs if isinstance(qs, list) else []
    return fixed


# -------------------------------------------------------------
# SAVE JSON
# -------------------------------------------------------------
def save_json(data):
    cleaned = {}
    for tab, qs in data.items():
        cl = []
        for q in qs:
            cl.append({k: clean(v) for k, v in q.items()})
        cleaned[tab] = cl

    raw_bytes = json.dumps(cleaned, indent=2).encode()
    meta = github_get(API).json()
    sha = meta.get("sha")

    r = github_put(API, raw_bytes, sha, "Update questions.json")

    if r.status_code not in (200, 201):
        st.error("❌ Opslaan mislukt!")
        st.code(r.text)
        return False

    # 🔧 FIX: Forceer een echte reload van load_data()
    st.session_state["reload_key"] = time.time()

    return True


# -------------------------------------------------------------
# UPLOAD IMAGE
# -------------------------------------------------------------
def upload_image(bytes, filename):
    path = f"{IMAGE_DIR}/{filename}"
    api = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"

    meta = github_get(api).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(bytes).decode()
    payload = {
        "message": f"Upload {filename}",
        "content": encoded
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(
        api,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )

    if r.status_code not in (200, 201):
        return None

    return (
        f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{path}"
    )


# -------------------------------------------------------------
# SESSION STATE
# -------------------------------------------------------------
if "mode" not in st.session_state:
    st.session_state.mode = "new"   # "new" / "edit"

if "edit_vak" not in st.session_state:
    st.session_state.edit_vak = None

if "edit_idx" not in st.session_state:
    st.session_state.edit_idx = None

# 🔧 reload_key default
if "reload_key" not in st.session_state:
    st.session_state.reload_key = 0


# -------------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------------
# 🔧 FIXED: load_data herlaadt nu ECHT
data = load_data(st.session_state.reload_key)


# -------------------------------------------------------------
# SELECT VAK
# -------------------------------------------------------------
st.subheader("📘 Kies een vak")
vak = st.selectbox("Vak:", list(data.keys()), key="vak_select")
vragen = data[vak]


# -------------------------------------------------------------
# LIJST MET VRAGEN
# -------------------------------------------------------------
st.subheader("📄 Overzicht vragen")

for i, q in enumerate(vragen):
    c1, c2, c3 = st.columns([7, 1, 1])

    with c1:
        st.write(f"**{i} — {q.get('text','')[:70]}**")

    with c2:
        if st.button("✏️", key=f"edit_btn_{vak}_{i}"):
            st.session_state.mode = "edit"
            st.session_state.edit_vak = vak
            st.session_state.edit_idx = i
            st.rerun()

    with c3:
        if st.button("❌", key=f"del_btn_{vak}_{i}"):
            vragen.pop(i)
            if save_json(data):
                st.success("Verwijderd!")
                st.rerun()


# -------------------------------------------------------------
# EDIT MODE FORM
# -------------------------------------------------------------
if st.session_state.mode == "edit":

    ev = st.session_state.edit_vak
    ei = st.session_state.edit_idx
    q = data[ev][ei]

    st.markdown("---")
    st.subheader(f"✏️ Vraag bewerken — [{ev}] #{ei}")

    text = st.text_input("Vraagtekst", value=q.get("text"), key="e_text")
    qtype = st.selectbox("Type", ["mc", "tf", "input"],
                         index=["mc", "tf", "input"].index(q.get("type")),
                         key="e_type")

    topic = st.text_input("Topic", value=q.get("topic"), key="e_topic")
    expl = st.text_area("Uitleg", value=q.get("explanation"), key="e_expl")

    if qtype == "mc":
        opts_str = ", ".join(q.get("choices"))
        opts = st.text_input("Opties", value=opts_str, key="e_opts")
        ans = st.number_input("Correct index", value=int(q.get("answer")), min_value=0, key="e_ans_mc")
    elif qtype == "tf":
        opts = ""
        ans = st.selectbox("Correct?", [True, False],
                           index=0 if q.get("answer") else 1,
                           key="e_ans_tf")
    else:
        opts = ""
        ans = st.text_input("Antwoord", value=str(q.get("answer")), key="e_ans_input")

    st.markdown("### Afbeelding")
    safe_img(q.get("image_url"))

    new_img = st.file_uploader("Nieuwe afbeelding", type=["png", "jpg", "jpeg"], key="e_img")
    rem_img = st.checkbox("Verwijder afbeelding", key="e_rem")

    if st.button("💾 Opslaan", key="save_edit"):
        q["text"] = text
        q["type"] = qtype
        q["topic"] = topic
        q["explanation"] = expl

        if qtype == "mc":
            q["choices"] = [s.strip() for s in opts.split(",") if s.strip()]
        else:
            q["choices"] = []

        q["answer"] = ans

        if rem_img:
            q["image_url"] = ""
        elif new_img:
            ext = new_img.name.split(".")[-1]
            fname = f"{ev}_{uuid.uuid4().hex[:6]}.{ext}"
            url = upload_image(new_img.read(), fname)
            if url:
                q["image_url"] = url

        if save_json(data):
            st.success("Opgeslagen!")
            st.session_state.mode = "new"
            st.rerun()

    if st.button("Annuleren", key="cancel_edit"):
        st.session_state.mode = "new"
        st.rerun()


# -------------------------------------------------------------
# NIEUWE VRAAG TOEVOEGEN
# -------------------------------------------------------------
if st.session_state.mode == "new":

    st.markdown("---")
    st.subheader("➕ Nieuwe vraag toevoegen")

    nt = st.text_input("Vraagtekst", key="n_text")
    ntp = st.selectbox("Type", ["mc", "tf", "input"], key="n_type")
    ntopic = st.text_input("Topic", key="n_topic")
    nexp = st.text_area("Uitleg", key="n_expl")

    if ntp == "mc":
        nop = st.text_input("Opties", key="n_opts")
        nans = st.number_input("Correct index", min_value=0, value=0, key="n_ans_mc")
    elif ntp == "tf":
        nop = ""
        nans = st.selectbox("Correct?", [True, False], key="n_ans_tf")
    else:
        nop = ""
        nans = st.text_input("Antwoord", key="n_ans_inp")

    nimg = st.file_uploader("Afbeelding", type=["png", "jpg", "jpeg"], key="n_img")

    if st.button("Toevoegen", key="btn_add"):
        if nt.strip() == "":
            st.error("Vraagtekst mag niet leeg zijn.")
        else:

            img = ""
            if nimg:
                ext = nimg.name.split(".")[-1]
                fname = f"{vak}_{uuid.uuid4().hex[:6]}.{ext}"
                url = upload_image(nimg.read(), fname)
                if url:
                    img = url

            newq = {
                "id": f"q{uuid.uuid4().hex[:6]}",
                "text": nt,
                "type": ntp,
                "topic": ntopic,
                "explanation": nexp,
                "choices": [s.strip() for s in nop.split(",")] if ntp == "mc" else [],
                "answer": nans,
                "image_url": img,
            }

            data[vak].append(newq)

            if save_json(data):
                st.success("Toegevoegd!")
                st.rerun()
