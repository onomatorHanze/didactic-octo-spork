import streamlit as st
import pandas as pd
import requests
import base64
import json
import time
import io
import ast

# ============================================================
# 🔧 GitHub configuratie (via Streamlit Secrets)
# ============================================================
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
FILE_PATH = st.secrets["FILE_PATH"]     # "data/quizvragen.xlsx"

IMAGE_DIR = "data/images"

RAW_EXCEL_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
EXCEL_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

API_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/vnd.github+json"
}

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# ============================================================
# 🖼 SAFE IMAGE LOADER (crash-safe)
# ============================================================
def safe_show_image(url: str, width: int = 350):
    """Toon afbeelding zonder Streamlit crash risico."""
    if not isinstance(url, str) or not url.strip():
        st.caption("Geen afbeelding gekoppeld.")
        return

    try:
        r = requests.get(url, timeout=4)
        if r.status_code != 200:
            st.caption("⚠️ Afbeelding kon niet geladen worden.")
            return
        st.image(r.content, width=width)
    except Exception:
        st.caption("⚠️ Afbeelding niet weer te geven.")


# ============================================================
# 📥 EXCEL LADEN
# ============================================================
@st.cache_data
def load_excel():
    tabs = pd.read_excel(RAW_EXCEL_URL, sheet_name=None, engine="openpyxl")

    # Zorg dat elke sheet image_url bevat
    for name, df in tabs.items():
        if "image_url" not in df.columns:
            df["image_url"] = ""
        tabs[name] = df

    return tabs


# ============================================================
# 📤 EXCEL OPSLAAN NAAR GITHUB
# ============================================================
def save_excel_to_github(tabs: dict) -> bool:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet, df in tabs.items():
            df.to_excel(writer, sheet_name=sheet, index=False)

    encoded = base64.b64encode(buf.getvalue()).decode()

    meta = requests.get(EXCEL_API_URL, headers=API_HEADERS).json()

    payload = {
        "message": "Update quizvragen via Admin",
        "content": encoded,
        "sha": meta.get("sha")
    }

    r = requests.put(EXCEL_API_URL, headers=API_HEADERS, data=json.dumps(payload))
    return r.status_code in (200, 201)


# ============================================================
# 🖼 AFBEELDING UPLOADEN
# ============================================================
def upload_image_to_github(file_bytes: bytes, filename: str) -> str | None:
    image_path = f"{IMAGE_DIR}/{filename}"
    image_url_api = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    meta = requests.get(image_url_api, headers=API_HEADERS).json()
    sha = meta.get("sha")

    payload = {
        "message": f"Upload {filename}",
        "content": base64.b64encode(file_bytes).decode()
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(image_url_api, headers=API_HEADERS, data=json.dumps(payload))

    if r.status_code not in (200, 201):
        st.error(f"❌ Upload mislukt (status {r.status_code})")
        try:
            st.code(r.text)
        except:
            pass
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{image_path}"


# ============================================================
# 🧠 SESSION STATE
# ============================================================
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None

if "delete_index" not in st.session_state:
    st.session_state.delete_index = None


# ============================================================
# 📚 VAKKEN LADEN
# ============================================================
tabs = load_excel()

st.subheader("📘 Kies een vak")
vak = st.selectbox("Vak", list(tabs.keys()))
df = tabs[vak]


# ============================================================
# 📄 OVERZICHT VRAGEN
# ============================================================
st.subheader("📄 Alle vragen")

for idx, row in df.iterrows():
    col1, col2, col3, col4 = st.columns([6, 1, 1, 1])

    with col1:
        text = str(row["text"])
        short = text[:80] + ("…" if len(text) > 80 else "")
        st.write(f"**{idx} — {short}**")

    with col2:
        img_url = str(row.get("image_url", "")).strip()
        if img_url:
            st.caption("🖼")

    with col3:
        if st.button("✏️", key=f"edit_{vak}_{idx}"):
            st.session_state.edit_index = idx
            st.session_state.delete_index = None
            st.rerun()

    with col4:
        if st.button("❌", key=f"del_{vak}_{idx}"):
            st.session_state.delete_index = idx
            st.session_state.edit_index = None
            st.rerun()


# ============================================================
# 🗑️ VERWIJDEREN
# ============================================================
if st.session_state.delete_index is not None:
    del_idx = st.session_state.delete_index

    st.markdown("---")
    st.subheader("❓ Vraag verwijderen?")
    st.write(f"**{del_idx} — {df.loc[del_idx, 'text']}**")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("✔ Ja verwijderen", key="delete_yes"):
            df = df.drop(del_idx).reset_index(drop=True)
            tabs[vak] = df
            if save_excel_to_github(tabs):
                st.cache_data.clear()
                st.success("Vraag verwijderd.")
                time.sleep(1)
                st.session_state.delete_index = None
                st.rerun()

    with c2:
        if st.button("✖ Annuleer", key="delete_no"):
            st.session_state.delete_index = None
            st.rerun()


# ============================================================
# ✏️ BEWERKEN
# ============================================================
if st.session_state.edit_index is not None:
    idx = st.session_state.edit_index
    question = df.loc[idx]

    st.markdown("---")
    st.subheader(f"✏️ Vraag {idx} bewerken")

    with st.container(border=True):
        edit_text = st.text_input("Vraagtekst", value=str(question["text"]))

        edit_type = st.selectbox(
            "Type",
            ["mc", "tf", "input"],
            index=["mc", "tf", "input"].index(question["type"])
        )

        st.markdown("#### Afbeelding")
        safe_show_image(question.get("image_url", ""))

        new_img = st.file_uploader("Nieuwe afbeelding", type=["png", "jpg", "jpeg"])
        remove_img = st.checkbox("Afbeelding verwijderen")

        # ---- Type-specifiek
        if edit_type == "mc":
            raw = question["choices"]
            try:
                opts = ast.literal_eval(raw)
            except:
                opts = []
            edit_opts = st.text_input("MC-opties", ", ".join(opts))
            edit_ans = st.number_input("Juiste index", min_value=0, value=int(question["answer"]))
        elif edit_type == "tf":
            edit_opts = ""
            edit_ans = st.selectbox("Correct?", [True, False], index=0 if bool(question["answer"]) else 1)
        else:
            edit_opts = ""
            edit_ans = st.text_input("Correct antwoord", str(question["answer"]))

        c1, c2 = st.columns([2, 1])

        with c1:
            if st.button("💾 Opslaan", key="save_edit"):
                df.loc[idx, "text"] = edit_text
                df.loc[idx, "type"] = edit_type
                df.loc[idx, "choices"] = str([s.strip() for s in edit_opts.split(",")]) if edit_type == "mc" else ""
                df.loc[idx, "answer"] = edit_ans

                if remove_img:
                    df.loc[idx, "image_url"] = ""
                elif new_img:
                    ext = new_img.name.split(".")[-1].lower()
                    filename = f"{vak.replace(' ','_')}_q{idx}_{int(time.time())}.{ext}"
                    url = upload_image_to_github(new_img.read(), filename)
                    if url:
                        df.loc[idx, "image_url"] = url

                tabs[vak] = df
                if save_excel_to_github(tabs):
                    st.cache_data.clear()
                    st.success("Vraag opgeslagen!")
                    time.sleep(1)
                    st.session_state.edit_index = None
                    st.rerun()

        with c2:
            if st.button("✖ Annuleer", key="cancel_edit"):
                st.session_state.edit_index = None
                st.rerun()


# ============================================================
# ➕ NIEUWE VRAAG TOEVOEGEN
# ============================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag")

new_text = st.text_input("Vraagtekst:", key="new_text")
new_type = st.selectbox("Type:", ["mc", "tf", "input"], key="new_type")

if new_type == "mc":
    new_opts = st.text_input("Opties:", key="new_opts")
    new_ans = st.number_input("Index juiste antwoord", min_value=0, key="new_ans")
elif new_type == "tf":
    new_opts = ""
    new_ans = st.selectbox("Correct?", [True, False], key="new_ans_tf")
else:
    new_opts = ""
    new_ans = st.text_input("Correct antwoord", key="new_ans_in")

new_img = st.file_uploader("Afbeelding", type=["png", "jpg", "jpeg"], key="new_img")

if st.button("➕ Toevoegen", key="add_new"):
    if not new_text.strip():
        st.error("Vraagtekst mag niet leeg zijn.")
        st.stop()

    img_url = ""
    if new_img:
        ext = new_img.name.split(".")[-1].lower()
        filename = f"{vak.replace(' ','_')}_new_{int(time.time())}.{ext}"
        uploaded = upload_image_to_github(new_img.read(), filename)
        if uploaded:
            img_url = uploaded

    row = {col: "" for col in df.columns}
    row.update({
        "text": new_text,
        "type": new_type,
        "choices": str([s.strip() for s in new_opts.split(",")]) if new_type == "mc" else "",
        "answer": new_ans,
        "image_url": img_url
    })

    df = df._append(row, ignore_index=True)
    tabs[vak] = df

    if save_excel_to_github(tabs):
        st.cache_data.clear()
        st.success("Vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
