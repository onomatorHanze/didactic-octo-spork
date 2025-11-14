import streamlit as st
import pandas as pd
import requests
import base64
import json
import time
import io
from PIL import Image
import io

def safe_image_show(url: str):
    """Laadt een afbeelding veilig. Geen crash als URL nog niet bestaat."""
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
        st.image(img, width=300)
    except Exception as e:
        st.warning("⚠ Afbeelding kan niet worden geladen (misschien nog niet beschikbaar).")
        st.caption(url)
# ============================================================
# 🔧 GitHub configuratie (via Streamlit Secrets)
# ============================================================
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
FILE_PATH = st.secrets["FILE_PATH"]      # bv: "data/quizvragen.xlsx"

IMAGE_DIR = "data/images"                # Upload-map in GitHub repo

# URLs
RAW_EXCEL_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
EXCEL_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# ============================================================
# 📥 Excel inlezen
# ============================================================
@st.cache_data
def load_excel():
    """Laad alle tabbladen uit de Excel in dict {sheet: DataFrame}."""
    tabs = pd.read_excel(RAW_EXCEL_URL, sheet_name=None, engine="openpyxl")

    for name, df in tabs.items():
        # Zorg dat kolom aanwezig is
        if "image_url" not in df.columns:
            df["image_url"] = ""
        tabs[name] = df

    return tabs


# ============================================================
# 📤 Excel uploaden naar GitHub
# ============================================================
def save_excel_to_github(tabs: dict) -> bool:
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet, df in tabs.items():
            df.to_excel(writer, sheet_name=sheet, index=False)

    excel_bytes = output.getvalue()
    encoded = base64.b64encode(excel_bytes).decode()

    # Huidige sha ophalen
    meta = requests.get(EXCEL_API_URL, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta.get("sha")

    payload = {
        "message": "Update quizvragen via Admin",
        "content": encoded,
        "sha": sha
    }

    r = requests.put(
        EXCEL_API_URL,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload)
    )

    return r.status_code in (200, 201)


# ============================================================
# 🖼 Afbeelding uploaden naar GitHub
# ============================================================
def upload_image_to_github(file_bytes: bytes, filename: str) -> str | None:
    image_path = f"{IMAGE_DIR}/{filename}"
    image_api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    # Bestaat al?
    meta = requests.get(image_api_url, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode()

    payload = {
        "message": f"Upload image {filename}",
        "content": encoded
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(
        image_api_url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload)
    )

    if r.status_code not in (200, 201):
        st.error("❌ Upload van afbeelding mislukt.")
        return None

    # Raw URL teruggeven
    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{image_path}"


# ============================================================
# 🧠 UI State
# ============================================================
if "edit_mode" not in st.session_state:
    st.session_state["edit_mode"] = None

if "delete_confirm" not in st.session_state:
    st.session_state["delete_confirm"] = None


# ============================================================
# 📚 Vakken inladen
# ============================================================
tabs = load_excel()

st.subheader("📘 Kies een vak / tabblad")
vak = st.selectbox("Vak", list(tabs.keys()))

df = tabs[vak]


# ============================================================
# 📄 Overzicht vragen
# ============================================================
st.subheader("📄 Alle vragen")

for index, row in df.iterrows():
    col1, col2, col3, col4 = st.columns([5, 1.5, 1.5, 1.5])

    with col1:
        text = row["text"]
        if len(text) > 80:
            text = text[:80] + "…"
        st.write(f"**{index} – {text}**")

    with col2:
        if isinstance(row.get("image_url"), str) and row["image_url"]:
            st.caption("🖼 afbeelding")

    with col3:
        if st.button("✏️", key=f"edit_{index}"):
            st.session_state["edit_mode"] = index
            st.session_state["delete_confirm"] = None
            st.rerun()

    with col4:
        if st.button("❌", key=f"delete_{index}"):
            st.session_state["delete_confirm"] = index
            st.session_state["edit_mode"] = None
            st.rerun()


# ============================================================
# 🗑️ Confirm delete
# ============================================================
if st.session_state["delete_confirm"] is not None:
    idx = st.session_state["delete_confirm"]
    st.markdown("---")
    st.subheader("❓ Weet je zeker dat je deze vraag wilt verwijderen?")
    st.write(f"**{idx} – {df.loc[idx, 'text']}**")

    colA, colB = st.columns([1, 1])

    with colA:
        if st.button("✔ Verwijderen"):
            df = df.drop(idx).reset_index(drop=True)
            tabs[vak] = df

            if save_excel_to_github(tabs):
                st.cache_data.clear()
                st.success("Vraag verwijderd!")
                time.sleep(1)
                st.session_state["delete_confirm"] = None
                st.rerun()

    with colB:
        if st.button("✖ Annuleer"):
            st.session_state["delete_confirm"] = None
            st.rerun()


# ============================================================
# ✏️ Bewerken (modal)
# ============================================================
if st.session_state["edit_mode"] is not None:
    edit_index = st.session_state["edit_mode"]
    vraag = df.loc[edit_index]

    st.markdown("---")
    st.subheader(f"✏️ Vraag {edit_index} bewerken")

    with st.container(border=True):
        edit_text = st.text_input("Vraagtekst", value=vraag["text"])

        edit_type = st.selectbox(
            "Vraagtype",
            ["mc", "tf", "input"],
            index=["mc", "tf", "input"].index(vraag["type"])
        )

        # Afbeelding
        st.markdown("#### Afbeelding")
        current_image = vraag.get("image_url") or ""

        if current_image:
            safe_image_show(current_image)
        else:
            st.caption("Geen afbeelding gekoppeld.")

        new_img_file = st.file_uploader(
            "Nieuwe afbeelding uploaden (optioneel)",
            type=["png", "jpg", "jpeg"]
        )

        remove_img = st.checkbox("Afbeelding verwijderen")

        # Type-specifieke velden
        if edit_type == "mc":
            options = eval(vraag["choices"]) if vraag["choices"] else []
            edit_choices = st.text_input("Opties (komma gescheiden)", ", ".join(options))
            edit_answer = st.number_input("Index juist antwoord", min_value=0, value=int(vraag["answer"]))

        elif edit_type == "tf":
            edit_choices = ""
            edit_answer = st.selectbox("Correct?", [True, False], index=0 if vraag["answer"] else 1)

        else:
            edit_choices = ""
            edit_answer = st.text_input("Correct antwoord", str(vraag["answer"]))

        colA, colB = st.columns([2, 1])

        with colA:
            if st.button("💾 Opslaan"):
                df.loc[edit_index, "text"] = edit_text
                df.loc[edit_index, "type"] = edit_type
                df.loc[edit_index, "choices"] = (
                    str(edit_choices.split(",")) if edit_type == "mc" else ""
                )
                df.loc[edit_index, "answer"] = edit_answer

                # Afbeelding verwerken
                if remove_img:
                    df.loc[edit_index, "image_url"] = ""
                elif new_img_file is not None:
                    ext = new_img_file.name.split(".")[-1].lower()
                    safe_vak = vak.replace(" ", "_")
                    filename = f"{safe_vak}_q{edit_index}_{int(time.time())}.{ext}"
                    new_url = upload_image_to_github(new_img_file.read(), filename)

                    if new_url:
                        df.loc[edit_index, "image_url"] = new_url

                tabs[vak] = df

                if save_excel_to_github(tabs):
                    st.cache_data.clear()
                    st.success("Opgeslagen!")
                    time.sleep(1)
                    st.session_state["edit_mode"] = None
                    st.rerun()

        with colB:
            if st.button("✖ Annuleer"):
                st.session_state["edit_mode"] = None
                st.rerun()


# ============================================================
# ➕ Nieuwe vraag toevoegen
# ============================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag")

new_text = st.text_input("Vraagtekst")
new_type = st.selectbox("Vraagtype", ["mc", "tf", "input"])

if new_type == "mc":
    new_opts = st.text_input("Opties (komma gescheiden)")
    new_ans = st.number_input("Index juiste antwoord", min_value=0)
elif new_type == "tf":
    new_opts = ""
    new_ans = st.selectbox("Correct?", [True, False])
else:
    new_opts = ""
    new_ans = st.text_input("Correct antwoord")

new_img = st.file_uploader("Afbeelding uploaden (optioneel)", type=["png", "jpg", "jpeg"])

if st.button("➕ Toevoegen"):
    if new_text.strip() == "":
        st.error("Vraagtekst mag niet leeg zijn.")
        st.stop()

    image_url = ""
    if new_img:
        ext = new_img.name.split(".")[-1]
        safe_vak = vak.replace(" ", "_")
        filename = f"{safe_vak}_new_{int(time.time())}.{ext}"
        image_url = upload_image_to_github(new_img.read(), filename) or ""

    new_row = {
        "text": new_text,
        "type": new_type,
        "choices": str(new_opts.split(",")) if new_type == "mc" else "",
        "answer": new_ans,
        "image_url": image_url
    }

    df = df._append(new_row, ignore_index=True)
    tabs[vak] = df

    if save_excel_to_github(tabs):
        st.cache_data.clear()
        st.success("Vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
