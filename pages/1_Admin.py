import streamlit as st
import json
import requests
import base64
import time
import math
import uuid

# -------------------------------------------------------------
# CONFIG (uit Streamlit Secrets)
# -------------------------------------------------------------
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
JSON_PATH = st.secrets["FILE_PATH"]  # bv. "data/questions.json"
IMAGE_DIR = "data/images"

# GitHub RAW URL (wordt dynamisch opgebouwd om caching te omzeilen)
def make_raw_url():
    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{JSON_PATH}?t={int(time.time())}"

JSON_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{JSON_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------
def clean(v):
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return v


def github_get(url):
    return requests.get(url, headers={"Authorization": f"token {TOKEN}"})


def github_put(url, bytes_content, sha, message):
    encoded = base64.b64encode(bytes_content).decode()
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha
    return requests.put(
        url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload)
    )


def safe_image(url):
    if not url or not isinstance(url, str):
        return
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            st.image(r.content, width=350)
    except:
        pass


# -------------------------------------------------------------
# JSON BESTAND LADEN
# -------------------------------------------------------------
def load_data():
    url = make_raw_url()  # <-- cache bypass
    r = github_get(url)

    if r.status_code != 200:
        st.error("Kan questions.json niet laden!")
        st.stop()

    try:
        data = r.json()
    except:
        st.error("JSON is corrupt of niet leesbaar.")
        st.stop()

    # Zorg dat elke tab een lijst is
    fixed = {}
    for tab, qs in data.items():
        fixed[tab] = qs if isinstance(qs, list) else []

    return fixed


# -------------------------------------------------------------
# JSON OPSLAAN NAAR GITHUB
# -------------------------------------------------------------
def save_json(data):
    cleaned = {}
    for tab, qs in data.items():
        cleaned_list = []
        for q in qs:
            q2 = {k: clean(v) for k, v in q.items()}  # schoonmaken
            cleaned_list.append(q2)
        cleaned[tab] = cleaned_list

    raw_bytes = json.dumps(cleaned, indent=2, ensure_ascii=False).encode("utf-8")

    meta = github_get(JSON_API_URL).json()
    sha = meta.get("sha")

    r = github_put(JSON_API_URL, raw_bytes, sha, "Update questions.json via Admin")

    if r.status_code not in (200, 201):
        st.error("❌ Opslaan mislukt!")
        st.code(r.text)
        return False

    # NA OPSLAAN cache van Streamlit leegmaken
    st.cache_data.clear()  # <-- essentieel

    return True


# -------------------------------------------------------------
# Upload afbeelding
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
# SESSION STATE INIT
# -------------------------------------------------------------
if "edit_mode" not in st.session_state:
    st.session_state["edit_mode"] = False  # False = nieuwe vraag, True = bewerken

if "edit_vak" not in st.session_state:
    st.session_state["edit_vak"] = None

if "edit_index" not in st.session_state:
    st.session_state["edit_index"] = None


# -------------------------------------------------------------
# DATA LADEN
# -------------------------------------------------------------
data = load_data()


# -------------------------------------------------------------
# VAK SELECTIE
# -------------------------------------------------------------
st.subheader("📘 Kies een vak")
vak = st.selectbox("Vak", list(data.keys()), key="vak_select")
vragen = data[vak]


# -------------------------------------------------------------
# OVERZICHT VRAGEN
# -------------------------------------------------------------
st.subheader("📄 Overzicht vragen")

for idx, q in enumerate(vragen):
    col1, col2, col3 = st.columns([6, 1, 1])
    with col1:
        tekst = q.get("text", "")
        st.write(f"**{idx} — {tekst[:60]}{'…' if len(tekst)>60 else ''}**")
    with col2:
        if q.get("image_url"):
            st.caption("🖼")
    with col3:
        if st.button("✏️", key=f"edit_{vak}_{idx}"):
            st.session_state["edit_mode"] = True
            st.session_state["edit_vak"] = vak
            st.session_state["edit_index"] = idx
            st.rerun()


# -------------------------------------------------------------
# BEWERK-MODUS
# -------------------------------------------------------------
if st.session_state["edit_mode"]:

    ev = st.session_state["edit_vak"]
    ei = st.session_state["edit_index"]
    q = data[ev][ei]

    st.markdown("---")
    st.subheader(f"✏️ Vraag bewerken — [{ev}] #{ei}")

    text = st.text_input("Vraagtekst", value=q.get("text", ""), key="edit_text")
    qtype = st.selectbox("Type", ["mc", "tf", "input"],
                         index=["mc", "tf", "input"].index(q.get("type")),
                         key="edit_type")

    topic = st.text_input("Topic", value=q.get("topic", ""), key="edit_topic")
    expl = st.text_area("Uitleg", value=q.get("explanation", ""), key="edit_expl")

    # type-specific
    if qtype == "mc":
        opts = q.get("choices", [])
        opts_str = ", ".join(opts)
        new_opts = st.text_input("Opties (komma gescheiden)" , value=opts_str, key="edit_opts")
        new_ans = st.number_input("Correcte index", value=int(q.get("answer", 0)), min_value=0, key="edit_ans")
    elif qtype == "tf":
        new_opts = ""
        new_ans = st.selectbox("Correct?", [True, False], index=0 if q.get("answer") else 1, key="edit_ans_tf")
    else:
        new_opts = ""
        new_ans = st.text_input("Correct antwoord", value=str(q.get("answer", "")), key="edit_ans_input")

    st.markdown("### Afbeelding")
    safe_image(q.get("image_url"))

    new_img = st.file_uploader("Nieuwe afbeelding", type=["png", "jpg", "jpeg"], key="edit_img")
    rem_img = st.checkbox("Afbeelding verwijderen", key="edit_remove_img")

    if st.button("💾 Opslaan", key="edit_save"):
        q["text"] = text
        q["type"] = qtype
        q["topic"] = topic
        q["explanation"] = expl

        if qtype == "mc":
            q["choices"] = [s.strip() for s in new_opts.split(",") if s.strip()]
        else:
            q["choices"] = []

        q["answer"] = new_ans

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
            st.session_state["edit_mode"] = False
            st.rerun()

    if st.button("Annuleer", key="edit_cancel"):
        st.session_state["edit_mode"] = False
        st.rerun()


# -------------------------------------------------------------
# NIEUWE VRAAG TOEVOEGEN (alleen zichtbaar als NIET in edit_mode)
# -------------------------------------------------------------
if not st.session_state["edit_mode"]:

    st.markdown("---")
    st.subheader("➕ Nieuwe vraag toevoegen")

    nt = st.text_input("Vraagtekst", key="new_text")
    ntype = st.selectbox("Type", ["mc", "tf", "input"], key="new_type2")
    ntopic = st.text_input("Topic", key="new_topic")
    nexp = st.text_area("Uitleg", key="new_expl")

    if ntype == "mc":
        nopts_str = st.text_input("Opties (komma gescheiden)", key="new_opts")
        nans = st.number_input("Correct index", min_value=0, value=0, key="new_ans")
    elif ntype == "tf":
        nopts_str = ""
        nans = st.selectbox("Correct?", [True, False], key="new_ans_tf")
    else:
        nopts_str = ""
        nans = st.text_input("Antwoord", key="new_ans_input")

    nimg = st.file_uploader("Afbeelding", type=["png", "jpg", "jpeg"], key="new_img2")

    if st.button("Toevoegen", key="add_new_btn2"):
        if nt.strip() == "":
            st.error("Vraagtekst mag niet leeg zijn.")
        else:
            img_url = ""
            if nimg:
                ext = nimg.name.split(".")[-1]
                fname = f"{vak}_{uuid.uuid4().hex[:6]}.{ext}"
                url = upload_image(nimg.read(), fname)
                if url:
                    img_url = url

            if ntype == "mc":
                opts = [s.strip() for s in nopts_str.split(",") if s.strip()]
            else:
                opts = []

            newq = {
                "id": f"q{uuid.uuid4().hex[:6]}",
                "text": nt,
                "type": ntype,
                "topic": ntopic,
                "explanation": nexp,
                "choices": opts,
                "answer": nans,
                "image_url": img_url,
            }

            data[vak].append(newq)

            if save_json(data):
                st.success("Nieuwe vraag toegevoegd!")
                time.sleep(1)
                st.rerun()
