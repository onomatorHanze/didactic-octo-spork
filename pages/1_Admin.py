import streamlit as st
import json
import requests
import base64
import uuid
import time
import math
import pandas as pd
import ast


# -------------------------------------------------------------
# SETTINGS & GITHUB CONFIG
# -------------------------------------------------------------
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
JSON_PATH = st.secrets["FILE_PATH"]
IMAGE_DIR = "data/images"

API_RAW = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{JSON_PATH}"

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


def github_put(url, bytes_data, sha, msg):
    encoded = base64.b64encode(bytes_data).decode()
    payload = {"message": msg, "content": encoded}
    if sha:
        payload["sha"] = sha
    return requests.put(
        url, headers={"Authorization": f"token {TOKEN}"}, data=json.dumps(payload)
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
# LOAD JSON (GitHub API)
# -------------------------------------------------------------
def load_data(_reload):
    r = github_get(API_RAW)
    if r.status_code != 200:
        st.error("Kon JSON niet laden via GitHub API!")
        st.code(r.text)
        st.stop()

    try:
        content = r.json().get("content", "")
        decoded = base64.b64decode(content).decode("utf-8")
        data = json.loads(decoded)
    except Exception as e:
        st.error("Kon JSON niet decoderen!")
        st.text(str(e))
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
        cleaned[tab] = [{k: clean(v) for k, v in q.items()} for q in qs]

    raw_bytes = json.dumps(cleaned, indent=2).encode()

    meta = github_get(API_RAW).json()
    sha = meta.get("sha")

    r = github_put(API_RAW, raw_bytes, sha, "Update questions.json")

    if r.status_code not in (200, 201):
        st.error("❌ Opslaan mislukt!")
        st.code(r.text)
        return False

    st.session_state["reload_key"] = time.time()
    return True


# -------------------------------------------------------------
# UPLOAD IMAGE
# -------------------------------------------------------------
def upload_image(bytes_data, filename):
    path = f"{IMAGE_DIR}/{filename}"
    api = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"

    meta = github_get(api).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(bytes_data).decode()
    payload = {"message": f"Upload {filename}", "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(
        api, headers={"Authorization": f"token {TOKEN}"}, data=json.dumps(payload)
    )

    if r.status_code not in (200, 201):
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{path}"


# -------------------------------------------------------------
# SESSION STATE
# -------------------------------------------------------------
st.session_state.setdefault("mode", "new")
st.session_state.setdefault("edit_vak", None)
st.session_state.setdefault("edit_idx", None)
st.session_state.setdefault("reload_key", 0)
st.session_state.setdefault("confirm_delete", None)
st.session_state.setdefault("confirm_delete_vak", None)


# -------------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------------
data = load_data(st.session_state.reload_key)


# -------------------------------------------------------------
# DEBUG INFO
# -------------------------------------------------------------
with st.expander("🐛 DEBUG INFO", expanded=False):
    st.write("Reload key:", st.session_state.reload_key)
    for tab in data:
        st.write(f"Vak '{tab}': {len(data[tab])} vragen")


# -------------------------------------------------------------
# SELECT VAK
# -------------------------------------------------------------
st.subheader("📘 Kies een vak")
vak = st.selectbox("Vak:", list(data.keys()) if data else [])

if vak:
    vragen = data[vak]
else:
    vragen = []

# -------------------------------------------------------------
# VAK TOEVOEGEN
# -------------------------------------------------------------
st.markdown("### ➕ Nieuw vak toevoegen")

new_vak = st.text_input("Nieuwe vaknaam:", key="new_vak_input")

if st.button("Vak toevoegen"):
    if st.session_state.mode == "edit":
        st.warning("Je kunt geen nieuw vak toevoegen terwijl je een vraag bewerkt.")
        st.stop()

    if not new_vak or new_vak.strip() == "":
        st.warning("Vul eerst een naam in.")
        st.stop()

    new_vak = new_vak.strip()

    if new_vak in data:
        st.error(f"Vak '{new_vak}' bestaat al!")
        st.stop()

    # nieuw vak toevoegen
    data[new_vak] = []

    if save_json(data):
        st.success(f"Vak '{new_vak}' toegevoegd!")
        st.session_state["new_vak_input"] = ""
        st.rerun()

# -------------------------------------------------------------
# VAK VERWIJDEREN
# -------------------------------------------------------------
st.markdown("### ⚠️ Vak beheren")

if vak and st.button(f"❌ Verwijder vak '{vak}'"):
    if st.session_state.mode == "edit":
        st.warning("Je kunt geen vak verwijderen terwijl je een vraag bewerkt.")
    else:
        st.session_state.confirm_delete_vak = vak
    st.rerun()

if st.session_state.confirm_delete_vak:
    dvak = st.session_state.confirm_delete_vak
    st.error(f"❗ Weet je zeker dat je het vak '{dvak}' wilt verwijderen?")
    st.write("Alle vragen in dit vak gaan verloren.")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Ja, verwijder vak"):
            try:
                data.pop(dvak)
                save_json(data)
                st.success(f"Vak '{dvak}' verwijderd.")
            except Exception as e:
                st.error(f"Fout bij verwijderen: {e}")
            st.session_state.confirm_delete_vak = None
            st.rerun()

    with c2:
        if st.button("Nee, annuleren"):
            st.session_state.confirm_delete_vak = None
            st.rerun()


# -------------------------------------------------------------
# OVERZICHT VRAGEN
# -------------------------------------------------------------
st.subheader("📄 Overzicht vragen")

for i, q in enumerate(vragen):
    c1, c2, c3 = st.columns([7, 1, 1])

    with c1:
        st.write(f"**{i} — {q.get('text', '')[:70]}**")

    with c2:
        if st.button("✏️", key=f"edit_{vak}_{i}"):
            st.session_state.mode = "edit"
            st.session_state.edit_vak = vak
            st.session_state.edit_idx = i
            st.rerun()

    with c3:
        if st.button("❌", key=f"del_{vak}_{i}"):

            if st.session_state.mode == "edit":
                st.warning("Je kunt geen vraag verwijderen terwijl je een vraag bewerkt.")
                st.session_state.confirm_delete = None
                st.rerun()

            st.session_state.confirm_delete = (vak, i)
            st.rerun()


# -------------------------------------------------------------
# CONFIRM DELETE QUESTION
# -------------------------------------------------------------
if st.session_state.confirm_delete:
    dvak, di = st.session_state.confirm_delete
    st.error(f"❗ Weet je zeker dat je vraag #{di} uit '{dvak}' wilt verwijderen?")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Ja, verwijderen"):
            try:
                data[dvak].pop(di)
                save_json(data)
                st.success("Vraag verwijderd.")
            except Exception as e:
                st.error(f"Fout bij verwijderen: {e}")
            st.session_state.confirm_delete = None
            st.rerun()

    with c2:
        if st.button("Nee, annuleren"):
            st.session_state.confirm_delete = None
            st.rerun()


# -------------------------------------------------------------
# EDIT MODE
# -------------------------------------------------------------
if st.session_state.mode == "edit":

    ev = st.session_state.edit_vak
    ei = st.session_state.edit_idx
    q = data[ev][ei]

    st.markdown("---")
    st.subheader(f"✏️ Vraag bewerken — [{ev}] #{ei}")

    text = st.text_input("Vraagtekst", value=q.get("text"))
    qtype = st.selectbox("Type", ["mc", "tf", "input"],
                         index=["mc", "tf", "input"].index(q.get("type")))

    topic = st.text_input("Topic", value=q.get("topic"))
    expl = st.text_area("Uitleg", value=q.get("explanation"))

    if qtype == "mc":
        opts_str = ", ".join(q.get("choices"))
        opts = st.text_input("Opties", value=opts_str)
        ans = st.number_input("Correct index", value=int(q.get("answer")),
                              min_value=0)
    elif qtype == "tf":
        opts = ""
        ans = st.selectbox("Correct?", [True, False],
                           index=0 if q.get("answer") else 1)
    else:
        opts = ""
        ans = st.text_input("Antwoord", value=str(q.get("answer")))

    st.markdown("### Afbeelding")
    safe_img(q.get("image_url"))

    new_img = st.file_uploader("Nieuwe afbeelding", type=["png", "jpg", "jpeg"])
    rem_img = st.checkbox("Verwijder afbeelding")

    if st.button("💾 Opslaan"):
        q["text"] = text
        q["type"] = qtype
        q["topic"] = topic
        q["explanation"] = expl

        q["choices"] = [s.strip() for s in opts.split(",")] if qtype == "mc" else []
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
            st.session_state.mode = "new"
            st.rerun()

    if st.button("Annuleren"):
        st.session_state.mode = "new"
        st.rerun()


# -------------------------------------------------------------
# EXCEL IMPORT
# -------------------------------------------------------------
st.markdown("---")
st.subheader("📥 Excel importeren")

excel_file = st.file_uploader("Upload een Excel-bestand (.xlsx)", type=["xlsx"])

if excel_file and st.button("Importeer Excel"):
    try:
        df = pd.read_excel(excel_file)

        required_cols = {"vak", "id", "type", "topic", "text", "answer"}
        if not required_cols.issubset(df.columns):
            st.error(f"Excel mist verplichte kolommen: {required_cols}")
            st.stop()

        count = 0

        for _, row in df.iterrows():
            dvak = str(row["vak"]).strip()

            if dvak not in data:
                data[dvak] = []

            q = {
                "id": str(row["id"]),
                "type": str(row["type"]),
                "topic": str(row.get("topic", "")),
                "text": str(row.get("text", "")),
                "choices": ast.literal_eval(str(row["choices"]))
                if str(row.get("choices")) not in ["", "nan", None]
                else [],
                "answer": row.get("answer"),
                "explanation": str(row.get("explanation", "")),
                "image_url": str(row.get("image_url", "")),
                "difficulty": int(row.get("difficulty", 1)),
            }

            data[dvak].append(q)
            count += 1

        if save_json(data):
            st.success(f"Succesvol {count} vragen geïmporteerd!")

    except Exception as e:
        st.error(f"❌ Fout bij importeren: {e}")


# -------------------------------------------------------------
# NIEUWE VRAAG TOEVOEGEN
# -------------------------------------------------------------
if st.session_state.mode == "new":

    st.markdown("---")
    st.subheader("➕ Nieuwe vraag toevoegen")

    nt = st.text_input("Vraagtekst")
    ntp = st.selectbox("Type", ["mc", "tf", "input"])
    ntopic = st.text_input("Topic")
    nexp = st.text_area("Uitleg")

    if ntp == "mc":
        nop = st.text_input("Opties")
        nans = st.number_input("Correct index", min_value=0, value=0)
    elif ntp == "tf":
        nop = ""
        nans = st.selectbox("Correct?", [True, False])
    else:
        nop = ""
        nans = st.text_input("Antwoord")

    nimg = st.file_uploader("Afbeelding", type=["png", "jpg", "jpeg"])

    if st.button("Toevoegen"):
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
