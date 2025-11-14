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
FILE_PATH = st.secrets["FILE_PATH"]         # bv: "data/quizvragen.xlsx"
IMAGE_DIR = "data/images"                   # map waar afbeeldingen worden opgeslagen

RAW_EXCEL_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
EXCEL_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# ============================================================
# 📥 Excel laden
# ============================================================
@st.cache_data
def load_excel():
    tabs = pd.read_excel(RAW_EXCEL_URL, sheet_name=None, engine="openpyxl")
    for name, df in tabs.items():
        if "image_url" not in df.columns:
            df["image_url"] = ""
        tabs[name] = df
    return tabs


# ============================================================
# 📤 Excel opslaan naar GitHub
# ============================================================
def save_excel_to_github(tabs):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet, df in tabs.items():
            df.to_excel(writer, sheet_name=sheet, index=False)

    encoded = base64.b64encode(buf.getvalue()).decode()

    meta = requests.get(EXCEL_API_URL, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta.get("sha")

    payload = {"message": "Update quizvragen via Admin", "content": encoded, "sha": sha}

    r = requests.put(
        EXCEL_API_URL,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )

    return r.status_code in (200, 201)


# ============================================================
# 🖼 Afbeelding uploaden naar GitHub
# ============================================================
def upload_image_to_github(file_bytes, filename):
    image_path = f"{IMAGE_DIR}/{filename}"
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    meta = requests.get(url, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode()

    payload = {"message": f"Upload image {filename}", "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers={"Authorization": f"token {TOKEN}"}, data=json.dumps(payload))

    if r.status_code not in (200, 201):
        st.error("❌ Upload afbeelding mislukt.")
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{image_path}"


# ============================================================
# 🧠 UI state
# ============================================================
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None

if "delete_index" not in st.session_state:
    st.session_state.delete_index = None


# ============================================================
# 📚 Vakkenlijst
# ============================================================
tabs = load_excel()

st.subheader("📘 Kies vak")
vak = st.selectbox("Vak:", list(tabs.keys()), key="vak_select")
df = tabs[vak]


# ============================================================
# 📄 Overzicht vragen
# ============================================================
st.subheader("📄 Alle vragen")

for idx, row in df.iterrows():
    col1, col2, col3, col4 = st.columns([5, 1.5, 1.5, 1.5])

    with col1:
        text = str(row["text"])
        st.write(f"**{idx} – {text[:80]}{'…' if len(text)>80 else ''}**")

    with col2:
        if row.get("image_url"):
            st.caption("🖼 afbeelding")

    with col3:
        if st.button("✏️", key=f"edit_btn_{vak}_{idx}"):
            st.session_state.edit_index = idx
            st.session_state.delete_index = None
            st.rerun()

    with col4:
        if st.button("❌", key=f"del_btn_{vak}_{idx}"):
            st.session_state.delete_index = idx
            st.session_state.edit_index = None
            st.rerun()


# ============================================================
# 🗑️ Verwijderen – bevestiging
# ============================================================
if st.session_state.delete_index is not None:
    idx = st.session_state.delete_index

    st.markdown("---")
    st.subheader("❓ Verwijderen bevestigen")
    st.write(f"**{idx} – {df.loc[idx, 'text']}**")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("✔ Ja, verwijderen", key=f"confirm_del_{idx}"):
            df = df.drop(idx).reset_index(drop=True)
            tabs[vak] = df
            save_excel_to_github(tabs)
            st.cache_data.clear()
            st.success("Verwijderd!")
            time.sleep(1)
            st.session_state.delete_index = None
            st.rerun()

    with c2:
        if st.button("✖ Nee", key=f"cancel_del_{idx}"):
            st.session_state.delete_index = None
            st.rerun()


# ============================================================
# ✏️ Bewerken – modal
# ============================================================
if st.session_state.edit_index is not None:
    idx = st.session_state.edit_index
    vraag = df.loc[idx]

    st.markdown("---")
    st.subheader(f"✏️ Vraag {idx} bewerken")

    with st.container(border=True):
        edit_text = st.text_input("Vraagtekst:", vraag["text"], key=f"edit_text_{idx}")

        types = ["mc", "tf", "input"]
        edit_type = st.selectbox(
            "Vraagtype:", types, index=types.index(vraag["type"]), key=f"edit_type_{idx}"
        )

        st.markdown("#### Afbeelding")
        img_url = vraag.get("image_url", "")

        if img_url:
            st.image(img_url, width=350)

        new_img = st.file_uploader("Nieuwe afbeelding uploaden", type=["png", "jpg", "jpeg"],
                                   key=f"edit_img_{idx}")

        remove_img = st.checkbox("Afbeelding verwijderen", key=f"edit_remove_{idx}")

        # Type specifieke velden
        if edit_type == "mc":
            raw = vraag.get("choices", "")
            try:
                parsed = ast.literal_eval(raw)
                opts = [str(x) for x in parsed]
            except:
                opts = []

            edit_choices = st.text_input("Opties:", ", ".join(opts), key=f"edit_opts_{idx}")
            edit_answer = st.number_input("Index juiste antwoord", min_value=0,
                                          value=int(vraag.get("answer", 0)),
                                          key=f"edit_ans_{idx}")

        elif edit_type == "tf":
            edit_choices = ""
            edit_answer = st.selectbox("Correct?", [True, False],
                                       index=0 if vraag["answer"] else 1,
                                       key=f"edit_tf_{idx}")

        else:
            edit_choices = ""
            edit_answer = st.text_input("Correct antwoord:", str(vraag.get("answer", "")),
                                        key=f"edit_input_{idx}")

        c1, c2 = st.columns([2, 1])

        with c1:
            if st.button("💾 Opslaan", key=f"save_edit_{idx}"):

                df.loc[idx, "text"] = edit_text
                df.loc[idx, "type"] = edit_type
                df.loc[idx, "choices"] = (
                    str([o.strip() for o in edit_choices.split(",")]) if edit_type == "mc" else ""
                )
                df.loc[idx, "answer"] = edit_answer

                if remove_img:
                    df.loc[idx, "image_url"] = ""
                elif new_img:
                    ext = new_img.name.split(".")[-1].lower()
                    filename = f"{vak.replace(' ', '_')}_q{idx}_{int(time.time())}.{ext}"
                    url = upload_image_to_github(new_img.read(), filename)
                    if url:
                        df.loc[idx, "image_url"] = url

                tabs[vak] = df
                save_excel_to_github(tabs)
                st.cache_data.clear()

                st.success("Opgeslagen!")
                time.sleep(1)
                st.session_state.edit_index = None
                st.rerun()

        with c2:
            if st.button("✖ Annuleer", key=f"cancel_edit_{idx}"):
                st.session_state.edit_index = None
                st.rerun()


# ============================================================
# ➕ Nieuwe vraag toevoegen
# ============================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag toevoegen")

new_text = st.text_input("Vraagtekst:", key="newq_text")
new_type = st.selectbox("Vraagtype:", ["mc", "tf", "input"], key="newq_type")

if new_type == "mc":
    new_opts = st.text_input("Opties (komma gescheiden):", key="newq_opts")
    new_ans = st.number_input("Index juiste antwoord", min_value=0, step=1, key="newq_ans_mc")

elif new_type == "tf":
    new_opts = ""
    new_ans = st.selectbox("Correct?", [True, False], key="newq_ans_tf")

else:
    new_opts = ""
    new_ans = st.text_input("Correct antwoord:", key="newq_ans_input")

new_img = st.file_uploader("Afbeelding uploaden", type=["png", "jpg", "jpeg"],
                           key="newq_img")


if st.button("➕ Toevoegen", key="newq_add"):
    if not new_text.strip():
        st.error("Vraagtekst verplicht.")
        st.stop()

    image_url = ""
    if new_img:
        ext = new_img.name.split(".")[-1].lower()
        filename = f"{vak.replace(' ', '_')}_new_{int(time.time())}.{ext}"
        url = upload_image_to_github(new_img.read(), filename)
        if url:
            image_url = url

    if new_type == "mc":
        opts = [s.strip() for s in new_opts.split(",") if s.strip()]
        choices_val = str(opts)
    else:
        choices_val = ""

    new_row = {
        "text": new_text,
        "type": new_type,
        "choices": choices_val,
        "answer": new_ans,
        "image_url": image_url,
    }

    df = df._append(new_row, ignore_index=True)
    tabs[vak] = df

    save_excel_to_github(tabs)
    st.cache_data.clear()

    st.success("🎉 Nieuwe vraag toegevoegd!")
    time.sleep(1)
    st.rerun()
