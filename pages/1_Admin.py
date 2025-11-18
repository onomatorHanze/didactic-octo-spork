import streamlit as st
import pandas as pd
import requests
import base64
import json
import time
import io
import ast

# ============================================================
# 🔧 GitHub configuratie
# ============================================================
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
FILE_PATH = st.secrets["FILE_PATH"]

IMAGE_DIR = "data/images"

RAW_EXCEL_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
EXCEL_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# ============================================================
# 🖼 Veilige image loader (crash-free)
# ============================================================
def safe_show_image(url: str, width=350):
    url = str(url or "").strip()
    if url == "":
        st.caption("Geen afbeelding.")
        return

    try:
        r = requests.get(url, timeout=4)
        if r.status_code != 200:
            st.caption("⚠️ Afbeelding kon niet geladen worden.")
            return
        st.image(r.content, width=width)
    except:
        st.caption("⚠️ Afbeelding niet weer te geven.")


# ============================================================
# 📥 Excel laden
# ============================================================
@st.cache_data
def load_excel():
    tabs = pd.read_excel(RAW_EXCEL_URL, sheet_name=None, engine="openpyxl")

    for name, df in tabs.items():
        if "image_url" not in df.columns:
            df["image_url"] = ""
        df["image_url"] = df["image_url"].astype(str)  # <- belangrijkste fix
        tabs[name] = df
    return tabs


# ============================================================
# 📤 Excel opslaan
# ============================================================
def save_excel_to_github(tabs: dict) -> bool:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet, df in tabs.items():
            df.to_excel(writer, sheet_name=sheet, index=False)

    content = base64.b64encode(buf.getvalue()).decode()

    meta = requests.get(EXCEL_API_URL, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta.get("sha")

    payload = {
        "message": "Update quizvragen via Admin",
        "content": content,
        "sha": sha,
    }

    r = requests.put(
        EXCEL_API_URL,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload)
    )

    return r.status_code in (200, 201)


# ============================================================
# 🖼 Afbeelding uploaden
# ============================================================
def upload_image_to_github(file_bytes: bytes, filename: str) -> str | None:
    image_path = f"{IMAGE_DIR}/{filename}"
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    # SHA ophalen (bestaat bestand al?)
    meta = requests.get(url, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta.get("sha")

    payload = {
        "message": f"Upload image {filename}",
        "content": base64.b64encode(file_bytes).decode()
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers={"Authorization": f"token {TOKEN}"}, data=json.dumps(payload))

    if r.status_code not in (200, 201):
        st.error("❌ Afbeelding upload mislukt.")
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{image_path}"


# ============================================================
# 🔧 Session state
# ============================================================
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "delete_index" not in st.session_state:
    st.session_state.delete_index = None


# ============================================================
# 📚 Vakken
# ============================================================
tabs = load_excel()

st.subheader("📘 Kies een vak")
vak = st.selectbox("Vak", list(tabs.keys()), key="vak_select")
df = tabs[vak]


# ============================================================
# 📄 Overzicht vragen
# ============================================================
st.subheader("📄 Alle vragen")

for idx, row in df.iterrows():
    col1, col2, col3, col4 = st.columns([5, 1, 1, 1])

    with col1:
        text = str(row["text"])
        st.write(f"**{idx} — {text}**")

    with col2:
        if str(row.get("image_url", "")).strip():
            st.caption("🖼")

    with col3:
        if st.button("✏️", key=f"edit_{vak}_{idx}"):
            st.session_state.edit_index = idx
            st.session_state.delete_index = None
            st.rerun()

    with col4:
        if st.button("❌", key=f"delete_{vak}_{idx}"):
            st.session_state.delete_index = idx
            st.session_state.edit_index = None
            st.rerun()


# ============================================================
# 🗑️ Delete bevestiging
# ============================================================
if st.session_state.delete_index is not None:
    idx = st.session_state.delete_index

    st.markdown("---")
    st.subheader("❗ Vraag verwijderen?")
    st.write(f"**{idx} — {df.loc[idx, 'text']}**")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("✔ Ja verwijderen"):
            df = df.drop(idx).reset_index(drop=True)
            tabs[vak] = df

            if save_excel_to_github(tabs):
                st.cache_data.clear()
                st.success("Vraag verwijderd!")
                time.sleep(1)
                st.session_state.delete_index = None
                st.rerun()

    with c2:
        if st.button("✖ Nee annuleren"):
            st.session_state.delete_index = None
            st.rerun()


# ============================================================
# ✏️ Vraag bewerken
# ============================================================
if st.session_state.edit_index is not None:
    idx = st.session_state.edit_index
    vraag = df.loc[idx]

    st.markdown("---")
    st.subheader(f"✏️ Vraag {idx} bewerken")

    with st.container(border=True):
        edit_text = st.text_input("Vraagtekst", value=str(vraag["text"]), key=f"edit_text_{idx}")

        edit_type = st.selectbox(
            "Vraagtype",
            ["mc", "tf", "input"],
            index=["mc", "tf", "input"].index(vraag.get("type", "mc")),
            key=f"edit_type_{idx}"
        )

        st.markdown("#### Afbeelding")
        safe_show_image(vraag.get("image_url", ""))

        new_img = st.file_uploader(
            "Nieuwe afbeelding uploaden",
            type=["png", "jpg", "jpeg"],
            key=f"edit_img_{idx}"
        )
        remove_img = st.checkbox("Afbeelding verwijderen", key=f"rm_img_{idx}")

        # MC velden
        if edit_type == "mc":
            raw = vraag.get("choices", "")
            try:
                parsed = ast.literal_eval(raw)
                opts = [str(x) for x in parsed] if isinstance(parsed, list) else []
            except:
                opts = []
            edit_choices = st.text_input("MC-opties (komma gescheiden)", ", ".join(opts), key=f"opt_{idx}")
            edit_answer = st.number_input("Index juiste antwoord", min_value=0,
                                          value=int(vraag.get("answer", 0)),
                                          key=f"ans_{idx}")

        elif edit_type == "tf":
            edit_choices = ""
            edit_answer = st.selectbox("Correct?", [True, False],
                                       index=0 if vraag.get("answer", True) else 1,
                                       key=f"tf_{idx}")

        else:
            edit_choices = ""
            edit_answer = st.text_input("Correct antwoord", value=str(vraag.get("answer", "")),
                                        key=f"inp_{idx}")

        # Opslaan
        if st.button("💾 Opslaan", key=f"save_{idx}"):
            df.loc[idx, "text"] = edit_text
            df.loc[idx, "type"] = edit_type
            df.loc[idx, "choices"] = (
                str([s.strip() for s in edit_choices.split(",")]) if edit_type == "mc" else ""
            )
            df.loc[idx, "answer"] = edit_answer

            # Afbeelding
            if remove_img:
                df.loc[idx, "image_url"] = ""
            elif new_img:
                ext = new_img.name.split(".")[-1]
                filename = f"{vak}_q{idx}_{int(time.time())}.{ext}"
                uploaded = upload_image_to_github(new_img.read(), filename)
                if uploaded:
                    df.loc[idx, "image_url"] = uploaded

            tabs[vak] = df

            if save_excel_to_github(tabs):
                st.cache_data.clear()
                st.success("Vraag bijgewerkt!")
                time.sleep(1)
                st.session_state.edit_index = None
                st.rerun()

        if st.button("✖ Annuleren", key=f"cancel_{idx}"):
            st.session_state.edit_index = None
            st.rerun()


# ============================================================
# ➕ Nieuwe vraag
# ============================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag toevoegen")

new_text = st.text_input("Vraagtekst:", key="new_text")
new_type = st.selectbox("Type:", ["mc", "tf", "input"], key="new_type")

if new_type == "mc":
    new_opts = st.text_input("MC-opties (komma gescheiden):", key="new_opts")
    new_ans = st.number_input("Index juiste antwoord", min_value=0, key="new_ans_mc")
elif new_type == "tf":
    new_opts = ""
    new_ans = st.selectbox("Correct?", [True, False], key="new_ans_tf")
else:
    new_opts = ""
    new_ans = st.text_input("Correct antwoord:", key="new_ans_input")

new_img = st.file_uploader("Afbeelding uploaden", type=["png", "jpg", "jpeg"], key="new_img")

if st.button("➕ Toevoegen", key="add_new"):
    if new_text.strip() == "":
        st.error("❌ Vraagtekst mag niet leeg zijn.")
        st.stop()

    img_url = ""
    if new_img:
        ext = new_img.name.split(".")[-1]
        filename = f"{vak}_new_{int(time.time())}.{ext}"
        uploaded = upload_image_to_github(new_img.read(), filename)
        if uploaded:
            img_url = uploaded

    choices = str([s.strip() for s in new_opts.split(",")]) if new_type == "mc" else ""

    df = df._append({
        "text": new_text,
        "type": new_type,
        "choices": choices,
        "answer": new_ans,
        "image_url": img_url
    }, ignore_index=True)

    tabs[vak] = df

    if save_excel_to_github(tabs):
        st.cache_data.clear()
        st.success("Nieuwe vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
