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

RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{JSON_PATH}"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{JSON_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin")


# -------------------------------------------------------------
# HELPER FUNCTIES
# -------------------------------------------------------------
def clean(v):
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return v


def github_get(url):
    return requests.get(url, headers={"Authorization": f"token {TOKEN}"})


def github_put(url, bytes_data, sha, msg):
    encoded = base64.b64encode(bytes_data).decode()
    payload = {"message": msg, "content": encoded}
    if sha:
        payload["sha"] = sha
    return requests.put(url,
                        headers={"Authorization": f"token {TOKEN}"},
                        data=json.dumps(payload))


def safe_img(url, width=350):
    if not url:
        return
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            st.image(r.content, width=width)
    except:
        pass


# -------------------------------------------------------------
# DATA LOAD & SAVE
# -------------------------------------------------------------
def load_data():
    """Laad altijd verse JSON."""
    url = f"{RAW_URL}?ts={int(time.time())}"
    r = github_get(url)

    if r.status_code != 200:
        st.error("❌ Kon JSON niet laden van GitHub.")
        st.code(r.text)
        st.stop()

    try:
        data = r.json()
    except:
        st.error("❌ JSON is corrupt.")
        st.stop()

    fixed = {}
    for tab, qs in data.items():
        fixed[tab] = qs if isinstance(qs, list) else []
    return fixed


def save_json(data):
    """Schrijf JSON naar GitHub."""
    cleaned = {tab: [{k: clean(v) for k, v in q.items()} for q in qs] for tab, qs in data.items()}
    raw_bytes = json.dumps(cleaned, indent=2, ensure_ascii=False).encode()

    meta_resp = github_get(API_URL)
    sha = None
    if meta_resp.status_code == 200:
        try:
            sha = meta_resp.json().get("sha")
        except:
            sha = None

    r = github_put(API_URL, raw_bytes, sha, "Update questions.json")

    if r.status_code not in (200, 201):
        st.error("❌ Opslaan mislukt!")
        st.code(r.text)
        return False

    # 👉 BELANGRIJK: Force reload
    st.session_state["_force_reload"] = uuid.uuid4().hex

    st.success("✅ Opgeslagen!")
    return True


def upload_image(bytes_data, filename):
    path = f"{IMAGE_DIR}/{filename}"
    api = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"

    meta = github_get(api)
    sha = None
    if meta.status_code == 200:
        try:
            sha = meta.json().get("sha")
        except:
            sha = None

    encoded = base64.b64encode(bytes_data).decode()
    payload = {"message": f"Upload {filename}", "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(api,
                     headers={"Authorization": f"token {TOKEN}"},
                     data=json.dumps(payload))

    if r.status_code not in (200, 201):
        st.error("❌ Upload mislukt!")
        st.code(r.text)
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{path}"


# -------------------------------------------------------------
# SESSION STATE INIT
# -------------------------------------------------------------
def init_session():
    st.session_state.setdefault("mode", "new")
    st.session_state.setdefault("edit_vak", None)
    st.session_state.setdefault("edit_idx", None)


init_session()


# -------------------------------------------------------------
# UI COMPONENTS
# -------------------------------------------------------------
def parse_mc_choices(raw):
    return [s.strip() for s in raw.split(",") if s.strip()] if raw else []


def render_question_row(vak, index, q, data):
    c1, c2, c3 = st.columns([7, 1, 1])

    title = q.get("text", "")
    short = (title[:70] + "…") if len(title) > 70 else title

    with c1:
        st.write(f"**{index} — {short}**")

    with c2:
        if st.button("✏️", key=f"edit_btn_{vak}_{index}"):
            st.session_state.mode = "edit"
            st.session_state.edit_vak = vak
            st.session_state.edit_idx = index
            st.rerun()

    with c3:
        if st.button("❌", key=f"del_btn_{vak}_{index}"):
            st.session_state.confirm_delete = (vak, index)


def handle_delete_if_needed(data):
    if "confirm_delete" not in st.session_state or st.session_state.confirm_delete is None:
        return

    vak, idx = st.session_state.confirm_delete

    st.warning(f"⚠️ Vraag #{idx} uit vak '{vak}' verwijderen?")
    c1, c2 = st.columns(2)

    with c1:
        if st.button("Ja, verwijderen"):
            try:
                data[vak].pop(idx)
            except:
                st.error("Kon de vraag niet verwijderen.")
                st.session_state.confirm_delete = None
                st.rerun()

            if save_json(data):
                st.session_state.confirm_delete = None
                st.rerun()

    with c2:
        if st.button("Annuleren"):
            st.session_state.confirm_delete = None
            st.rerun()


# -------------------------------------------------------------
# EDIT FORM
# -------------------------------------------------------------
def render_edit_form(vak, idx, data):
    try:
        q = data[vak][idx]
    except:
        st.error("Vraag niet gevonden.")
        st.session_state.mode = "new"
        return

    st.markdown("---")
    st.subheader(f"✏️ Vraag bewerken — [{vak}] #{idx}")

    text = st.text_input("Vraagtekst", value=q.get("text", ""))
    qtype = st.selectbox("Type", ["mc", "tf", "input"], index=["mc", "tf", "input"].index(q.get("type", "mc")))
    topic = st.text_input("Topic", value=q.get("topic", ""))
    expl = st.text_area("Uitleg", value=q.get("explanation", ""))

    if qtype == "mc":
        opts = st.text_input("Opties", value=", ".join(q.get("choices", [])))
        ans = st.number_input("Correct index", value=int(q.get("answer", 0)))
    elif qtype == "tf":
        opts = ""
        ans = st.selectbox("Correct?", [True, False], index=0 if q.get("answer") else 1)
    else:
        opts = ""
        ans = st.text_input("Antwoord", value=str(q.get("answer", "")))

    st.markdown("### Afbeelding")
    safe_img(q.get("image_url"))
    new_img = st.file_uploader("Nieuwe afbeelding", type=["png", "jpg", "jpeg"])
    rem_img = st.checkbox("Verwijder afbeelding")

    if st.button("💾 Opslaan"):
        q["text"] = text
        q["type"] = qtype
        q["topic"] = topic
        q["explanation"] = expl
        q["choices"] = parse_mc_choices(opts) if qtype == "mc" else []
        q["answer"] = ans

        if rem_img:
            q["image_url"] = ""
        elif new_img:
            ext = new_img.name.split(".")[-1]
            fname = f"{vak}_{uuid.uuid4().hex[:6]}.{ext}"
            url = upload_image(new_img.read(), fname)
            if url:
                q["image_url"] = url

        if save_json(data):
            st.session_state.mode = "new"
            st.rerun()

    if st.button("Annuleren"):
        st.session_state.mode = "new"
        st.rerun()


# -------------------------------------------------------------
# NEW QUESTION FORM
# -------------------------------------------------------------
def render_new_question_form(vak, data):
    st.markdown("---")
    st.subheader("➕ Nieuwe vraag toevoegen")

    nt = st.text_input("Vraagtekst")
    ntp = st.selectbox("Type", ["mc", "tf", "input"])
    ntopic = st.text_input("Topic")
    nexp = st.text_area("Uitleg")

    if ntp == "mc":
        nop = st.text_input("Opties")
        ans = st.number_input("Correct index", min_value=0)
        choices = parse_mc_choices(nop)
    elif ntp == "tf":
        choices = []
        ans = st.selectbox("Correct?", [True, False])
    else:
        choices = []
        ans = st.text_input("Antwoord")

    nimg = st.file_uploader("Afbeelding", type=["png", "jpg", "jpeg"])

    if st.button("Toevoegen"):
        if nt.strip() == "":
            st.error("❌ Vraagtekst mag niet leeg zijn.")
            return

        img_url = ""
        if nimg:
            ext = nimg.name.split(".")[-1]
            fname = f"{vak}_{uuid.uuid4().hex[:6]}.{ext}"
            url = upload_image(nimg.read(), fname)
            if url:
                img_url = url

        newq = {
            "id": f"q{uuid.uuid4().hex[:6]}",
            "text": nt,
            "type": ntp,
            "topic": ntopic,
            "explanation": nexp,
            "choices": choices,
            "answer": ans,
            "image_url": img_url,
        }

        data[vak].append(newq)

        if save_json(data):
            st.rerun()


# -------------------------------------------------------------
# MAIN LOGICA
# -------------------------------------------------------------
def main():
    # 👉 Force reload key om load_data te refreshen
    reload_key = st.session_state.get("_force_reload", None)

    data = load_data()

    st.subheader("📘 Kies een vak")
    vak = st.selectbox("Vak:", list(data.keys()))
    vragen = data[vak]

    st.subheader("📄 Overzicht vragen")
    for i, q in enumerate(vragen):
        render_question_row(vak, i, q, data)

    handle_delete_if_needed(data)

    if st.session_state.mode == "edit":
        render_edit_form(st.session_state.edit_vak, st.session_state.edit_idx, data)
    else:
        render_new_question_form(vak, data)


main()
