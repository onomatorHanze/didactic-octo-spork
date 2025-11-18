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
FILE_PATH = st.secrets["FILE_PATH"]  # bv. "data/quizvragen.xlsx"

IMAGE_DIR = "data/images"

RAW_EXCEL_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
EXCEL_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# ============================================================
# 🖼 Veilige image viewer
# ============================================================
def safe_show_image(url: str, width=350):
    if not url or not isinstance(url, str) or not url.strip():
        st.caption("Geen afbeelding.")
        return
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            st.image(r.content, width=width)
        else:
            st.caption("⚠️ Afbeelding kon niet geladen worden.")
    except Exception:
        st.caption("⚠️ Afbeelding niet weer te geven.")


# ============================================================
# 📥 Excel inlezen
# ============================================================
@st.cache_data
def load_excel():
    tabs = pd.read_excel(RAW_EXCEL_URL, sheet_name=None, engine="openpyxl")
    for name, df in tabs.items():
        if "image_url" not in df.columns:
            df["image_url"] = ""
    return tabs


# ============================================================
# 📤 Excel opslaan
# ============================================================
def save_excel_to_github(tabs):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet, df in tabs.items():
            df.to_excel(writer, sheet_name=sheet, index=False)

    encoded = base64.b64encode(buf.getvalue()).decode()

    meta = requests.get(EXCEL_API_URL,
                        headers={"Authorization": f"token {TOKEN}"}).json()

    payload = {
        "message": "Update quizvragen via Admin",
        "content": encoded,
        "sha": meta.get("sha")
    }

    r = requests.put(EXCEL_API_URL,
                     headers={"Authorization": f"token {TOKEN}"},
                     data=json.dumps(payload))

    return r.status_code in (200, 201)


# ============================================================
# 🖼 Afbeelding upload
# ============================================================
def upload_image_to_github(file_bytes, filename):
    image_path = f"{IMAGE_DIR}/{filename}"
    api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    meta = requests.get(api_url, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta.get("sha")

    payload = {
        "message": f"Upload image {filename}",
        "content": base64.b64encode(file_bytes).decode()
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(
        api_url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload)
    )

    if r.status_code not in (200, 201):
        st.error("❌ Upload mislukt.")
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{image_path}"


# ============================================================
# 🧠 Session State
# ============================================================
st.session_state.setdefault("edit_index", None)
st.session_state.setdefault("delete_index", None)


# ============================================================
# 📚 Laad vakken
# ============================================================
tabs = load_excel()

st.subheader("📘 Kies een vak")
vak = st.selectbox("Vak", list(tabs.keys()))
df = tabs[vak]


# ============================================================
# 📄 Overzicht vragen
# ============================================================
st.subheader("📄 Alle vragen")

for idx, row in df.iterrows():
    col1, col2, col3, col4 = st.columns([5, 1, 1, 1])

    with col1:
        text = str(row["text"])
        st.write(f"**{idx} – {text[:80]}{'…' if len(text) > 80 else ''}**")

    with col2:
        if row.get("image_url"):
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
# 🗑️ DELETE CONFIRM
# ============================================================
if st.session_state.delete_index is not None:
    idx = st.session_state.delete_index

    # Veiligheidscheck
    if idx not in df.index:
        st.session_state.delete_index = None
        st.rerun()

    st.markdown("---")
    st.subheader("❓ Deze vraag verwijderen?")
    st.write(f"**{idx} – {df.loc[idx, 'text']}**")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("✔ Verwijderen", key="delete_yes"):
            df = df.drop(idx).reset_index(drop=True)
            tabs[vak] = df

            if save_excel_to_github(tabs):
                st.cache_data.clear()
                st.session_state.delete_index = None
                st.success("Vraag verwijderd!")
                time.sleep(1)
                st.rerun()

    with c2:
        if st.button("✖ Annuleer", key="delete_no"):
            st.session_state.delete_index = None
            st.rerun()


# ============================================================
# ✏️ Bewerken
# ============================================================
if st.session_state.edit_index is not None:
    idx = st.session_state.edit_index

    # Veiligheidscheck
    if idx not in df.index:
        st.session_state.edit_index = None
        st.rerun()

    vraag = df.loc[idx]

    st.markdown("---")
    st.subheader(f"✏️ Vraag {idx} bewerken")

    with st.container(border=True):

        text = st.text_input("Vraagtekst", value=vraag["text"], key=f"text_{idx}")

        types = ["mc", "tf", "input"]
        qtype = vraag.get("type", "mc")
        if qtype not in types:
            qtype = "mc"

        type_val = st.selectbox(
            "Vraagtype",
            types,
            index=types.index(qtype),
            key=f"type_{idx}"
        )

        st.markdown("#### Afbeelding")
        safe_show_image(vraag.get("image_url"))

        new_img = st.file_uploader(
            "Nieuwe afbeelding uploaden (optioneel)",
            type=["png", "jpg", "jpeg"],
            key=f"newimg_{idx}"
        )
        remove_img = st.checkbox("Afbeelding verwijderen", key=f"removeimg_{idx}")

        if type_val == "mc":
            raw = vraag.get("choices", "")
            try:
                opts = ast.literal_eval(raw) if raw else []
            except:
                opts = []

            opt_val = st.text_input(
                "Opties (komma gescheiden)",
                value=", ".join(opts),
                key=f"opts_{idx}"
            )
            ans_val = st.number_input(
                "Correcte index",
                min_value=0,
                step=1,
                value=int(vraag.get("answer", 0)),
                key=f"ans_mc_{idx}"
            )

        elif type_val == "tf":
            opt_val = ""
            ans_val = st.selectbox(
                "Correct?",
                [True, False],
                index=0 if vraag.get("answer") else 1,
                key=f"ans_tf_{idx}"
            )

        else:
            opt_val = ""
            ans_val = st.text_input(
                "Correct antwoord",
                value=str(vraag.get("answer", "")),
                key=f"ans_inp_{idx}"
            )

        save, cancel = st.columns(2)

        with save:
            if st.button("💾 Opslaan", key=f"save_{idx}"):

                df.loc[idx, "text"] = text
                df.loc[idx, "type"] = type_val
                df.loc[idx, "choices"] = str([s.strip() for s in opt_val.split(",")]) if type_val == "mc" else ""
                df.loc[idx, "answer"] = ans_val

                # Afbeelding
                if remove_img:
                    df.loc[idx, "image_url"] = ""
                elif new_img:
                    ext = new_img.name.split(".")[-1].lower()
                    filename = f"{vak.replace(' ', '_')}_{idx}_{int(time.time())}.{ext}"
                    url = upload_image_to_github(new_img.read(), filename)
                    if url:
                        df.loc[idx, "image_url"] = url

                tabs[vak] = df
                if save_excel_to_github(tabs):
                    st.cache_data.clear()
                    st.session_state.edit_index = None
                    st.success("Opgeslagen!")
                    time.sleep(1)
                    st.rerun()

        with cancel:
            if st.button("✖ Annuleer", key=f"cancel_{idx}"):
                st.session_state.edit_index = None
                st.rerun()


# ============================================================
# ➕ Nieuwe vraag
# ============================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag")

new_text = st.text_input("Vraagtekst", key="new_text")
new_type = st.selectbox("Type", ["mc", "tf", "input"], key="new_type")

if new_type == "mc":
    new_opts = st.text_input("Opties (komma gescheiden)", key="new_opts")
    new_ans = st.number_input("Correcte index", min_value=0, step=1, key="new_ans_mc")
elif new_type == "tf":
    new_opts = ""
    new_ans = st.selectbox("Correct?", [True, False], key="new_ans_tf")
else:
    new_opts = ""
    new_ans = st.text_input("Correct antwoord", key="new_ans_inp")

new_img = st.file_uploader(
    "Afbeelding uploaden",
    type=["png", "jpg", "jpeg"],
    key="new_img"
)

if st.button("➕ Toevoegen", key="new_add"):

    if new_text.strip() == "":
        st.error("❌ Vraagtekst mag niet leeg zijn.")
        st.stop()

    img_url = ""
    if new_img:
        ext = new_img.name.split(".")[-1].lower()
        filename = f"{vak.replace(' ', '_')}_new_{int(time.time())}.{ext}"
        url = upload_image_to_github(new_img.read(), filename)
        if url:
            img_url = url

    df = df._append({
        "text": new_text,
        "type": new_type,
        "choices": str([s.strip() for s in new_opts.split(",")]) if new_type == "mc" else "",
        "answer": new_ans,
        "image_url": img_url
    }, ignore_index=True)

    tabs[vak] = df

    if save_excel_to_github(tabs):
        st.cache_data.clear()
        st.success("Nieuwe vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
