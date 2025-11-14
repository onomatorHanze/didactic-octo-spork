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
FILE_PATH = st.secrets["FILE_PATH"]      # bv. "data/quizvragen.xlsx"

IMAGE_DIR = "data/images"                # Map in repo voor uploads

RAW_EXCEL_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
EXCEL_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# ============================================================
# 📥 Excel inlezen
# ============================================================
@st.cache_data
def load_excel() -> dict:
    """Laad alle tabbladen uit de Excel in dict {sheet_name: DataFrame}."""
    tabs = pd.read_excel(RAW_EXCEL_URL, sheet_name=None, engine="openpyxl")

    # Zorg dat elke sheet een image_url-kolom heeft
    for name, df in tabs.items():
        if "image_url" not in df.columns:
            df["image_url"] = ""
        tabs[name] = df

    return tabs


# ============================================================
# 📤 Excel opslaan naar GitHub
# ============================================================
def save_excel_to_github(tabs: dict) -> bool:
    """Schrijf alle sheets terug naar Excel en upload naar GitHub."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet_name, df in tabs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    excel_bytes = buf.getvalue()
    encoded = base64.b64encode(excel_bytes).decode()

    meta = requests.get(EXCEL_API_URL,
                        headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta.get("sha")

    payload = {
        "message": "Update quizvragen via Admin",
        "content": encoded,
        "sha": sha
    }

    r = requests.put(
        EXCEL_API_URL,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )
    return r.status_code in (200, 201)


# ============================================================
# 🖼 Afbeelding uploaden naar GitHub
# ============================================================
def upload_image_to_github(file_bytes: bytes, filename: str) -> str | None:
    """Upload een afbeelding naar data/images/<filename> in de repo."""
    image_path = f"{IMAGE_DIR}/{filename}"
    image_api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    # Check of hij al bestaat
    meta = requests.get(image_api_url,
                        headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode()
    payload = {
        "message": f"Upload image {filename}",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(
        image_api_url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )

    if r.status_code not in (200, 201):
        st.error("❌ Upload van afbeelding naar GitHub is mislukt.")
        return None

    # Raw URL teruggeven
    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{image_path}"


# ============================================================
# 🧠 UI state
# ============================================================
if "edit_index" not in st.session_state:
    st.session_state["edit_index"] = None

if "confirm_delete_index" not in st.session_state:
    st.session_state["confirm_delete_index"] = None


# ============================================================
# 📚 Vakken laden
# ============================================================
tabs = load_excel()

st.subheader("📘 Kies een vak / tabblad")
vak = st.selectbox("Vak", list(tabs.keys()), key="vak_select")

df = tabs[vak]


# ============================================================
# 📄 Overzicht vragen
# ============================================================
st.subheader("📄 Alle vragen in dit vak")

for idx, row in df.iterrows():
    col1, col2, col3, col4 = st.columns([5, 1.5, 1.5, 1.5])

    with col1:
        text = str(row.get("text", ""))
        if len(text) > 80:
            text = text[:80] + "…"
        st.write(f"**{idx} – {text}**")

    with col2:
        if isinstance(row.get("image_url"), str) and row["image_url"].strip():
            st.caption("🖼 afbeelding")

    with col3:
        if st.button("✏️", key=f"edit_btn_{vak}_{idx}"):
            st.session_state["edit_index"] = idx
            st.session_state["confirm_delete_index"] = None
            st.rerun()

    with col4:
        if st.button("❌", key=f"del_btn_{vak}_{idx}"):
            st.session_state["confirm_delete_index"] = idx
            st.session_state["edit_index"] = None
            st.rerun()


# ============================================================
# 🗑️ Verwijderen – bevestiging
# ============================================================
if st.session_state["confirm_delete_index"] is not None:
    del_idx = st.session_state["confirm_delete_index"]

    if del_idx < len(df):
        st.markdown("---")
        st.subheader("❓ Weet je zeker dat je deze vraag wilt verwijderen?")
        st.write(f"**{del_idx} – {df.loc[del_idx, 'text']}**")

        c1, c2 = st.columns([1, 1])

        with c1:
            if st.button("✔ Ja, verwijderen", key="confirm_delete_yes"):
                df = df.drop(del_idx).reset_index(drop=True)
                tabs[vak] = df

                if save_excel_to_github(tabs):
                    st.cache_data.clear()
                    st.success("Vraag verwijderd!")
                    time.sleep(1)
                    st.session_state["confirm_delete_index"] = None
                    st.rerun()
                else:
                    st.error("❌ Fout bij uploaden van Excel.")

        with c2:
            if st.button("✖ Nee, annuleren", key="confirm_delete_no"):
                st.session_state["confirm_delete_index"] = None
                st.rerun()


# ============================================================
# ✏️ Bewerken – “modal”
# ============================================================
if st.session_state["edit_index"] is not None:
    edit_idx = st.session_state["edit_index"]

    if edit_idx < len(df):
        vraag = df.loc[edit_idx]

        st.markdown("---")
        st.subheader(f"✏️ Vraag {edit_idx} bewerken")

        with st.container(border=True):
            # Basisvelden
            edit_text = st.text_input(
                "Vraagtekst",
                value=str(vraag.get("text", "")),
                key=f"edit_text_{edit_idx}",
            )

            current_type = str(vraag.get("type", "mc"))
            type_options = ["mc", "tf", "input"]
            if current_type not in type_options:
                current_type = "mc"
            edit_type = st.selectbox(
                "Vraagtype",
                type_options,
                index=type_options.index(current_type),
                key=f"edit_type_{edit_idx}",
            )

            # Afbeelding
            st.markdown("#### Afbeelding")
            raw_image = vraag.get("image_url", "")
            current_image = raw_image if isinstance(raw_image, str) else ""

            if current_image.strip():
                # vaste breedte => automatische schaal
                st.image(current_image, width=350)
            else:
                st.caption("Geen afbeelding gekoppeld.")

            new_img_file = st.file_uploader(
                "Nieuwe afbeelding uploaden (optioneel)",
                type=["png", "jpg", "jpeg"],
                key=f"edit_img_{edit_idx}",
            )

            remove_img = st.checkbox(
                "Afbeelding verwijderen",
                key=f"edit_remove_img_{edit_idx}",
            )

            # Type-specifieke velden
            if edit_type == "mc":
                raw_choices = vraag.get("choices", "")
                options_list: list[str] = []
                if isinstance(raw_choices, str) and raw_choices.strip():
                    try:
                        parsed = ast.literal_eval(raw_choices)
                        if isinstance(parsed, (list, tuple)):
                            options_list = [str(x) for x in parsed]
                    except Exception:
                        options_list = []
                edit_choices = st.text_input(
                    "MC-opties (komma gescheiden)",
                    ", ".join(options_list),
                    key=f"edit_choices_{edit_idx}",
                )
                edit_answer = st.number_input(
                    "Index juiste antwoord (0 = eerste)",
                    min_value=0,
                    value=int(vraag.get("answer", 0)),
                    key=f"edit_answer_{edit_idx}",
                )

            elif edit_type == "tf":
                edit_choices = ""
                current_tf = bool(vraag.get("answer", True))
                edit_answer = st.selectbox(
                    "Correct?",
                    [True, False],
                    index=0 if current_tf else 1,
                    key=f"edit_tf_{edit_idx}",
                )

            else:  # input
                edit_choices = ""
                edit_answer = st.text_input(
                    "Correct antwoord",
                    str(vraag.get("answer", "")),
                    key=f"edit_input_{edit_idx}",
                )

            c1, c2 = st.columns([2, 1])

            with c1:
                if st.button("💾 Opslaan", key="save_edit_btn"):
                    # Basisvelden updaten
                    df.loc[edit_idx, "text"] = edit_text
                    df.loc[edit_idx, "type"] = edit_type
                    df.loc[edit_idx, "choices"] = (
                        str([s.strip() for s in edit_choices.split(",")])
                        if edit_type == "mc"
                        else ""
                    )
                    df.loc[edit_idx, "answer"] = edit_answer

                    # Afbeelding verwerken
                    if "image_url" not in df.columns:
                        df["image_url"] = ""

                    if remove_img:
                        df.loc[edit_idx, "image_url"] = ""
                    elif new_img_file is not None:
                        ext = new_img_file.name.split(".")[-1].lower()
                        if ext not in ("png", "jpg", "jpeg"):
                            st.error("❌ Ongeldig afbeeldingsformaat.")
                        else:
                            safe_vak = vak.replace(" ", "_")
                            filename = f"{safe_vak}_q{edit_idx}_{int(time.time())}.{ext}"
                            new_url = upload_image_to_github(
                                new_img_file.read(), filename
                            )
                            if new_url:
                                df.loc[edit_idx, "image_url"] = new_url

                    tabs[vak] = df

                    if save_excel_to_github(tabs):
                        st.cache_data.clear()
                        st.success("Vraag opgeslagen!")
                        time.sleep(1)
                        st.session_state["edit_index"] = None
                        st.rerun()
                    else:
                        st.error("❌ Fout bij uploaden van Excel.")

            with c2:
                if st.button("✖ Annuleer", key="cancel_edit_btn"):
                    st.session_state["edit_index"] = None
                    st.rerun()


# ============================================================
# ➕ Nieuwe vraag toevoegen
# ============================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag")

new_text = st.text_input("Vraagtekst", key="new_text")
new_type = st.selectbox(
    "Vraagtype", ["mc", "tf", "input"], key="new_type_select"
)

if new_type == "mc":
    new_opts = st.text_input(
        "MC-opties (komma gescheiden)", key="new_opts"
    )
    new_ans = st.number_input(
        "Index juiste antwoord (0 = eerste)",
        min_value=0,
        key="new_ans_mc",
    )
elif new_type == "tf":
    new_opts = ""
    new_ans = st.selectbox(
        "Correct?", [True, False], key="new_ans_tf"
    )
else:
    new_opts = ""
    new_ans = st.text_input(
        "Correct antwoord", key="new_ans_input"
    )

new_img = st.file_uploader(
    "Afbeelding uploaden (optioneel)",
    type=["png", "jpg", "jpeg"],
    key="new_img_upload",
)

if st.button("➕ Toevoegen", key="add_new_btn"):
    if new_text.strip() == "":
        st.error("Vraagtekst mag niet leeg zijn.")
        st.stop()

    image_url = ""
    if new_img is not None:
        ext = new_img.name.split(".")[-1].lower()
        if ext not in ("png", "jpg", "jpeg"):
            st.error("❌ Ongeldig afbeeldingsformaat.")
            st.stop()
        safe_vak = vak.replace(" ", "_")
        filename = f"{safe_vak}_new_{int(time.time())}.{ext}"
        uploaded_url = upload_image_to_github(new_img.read(), filename)
        if uploaded_url:
            image_url = uploaded_url

    new_row = {
        "text": new_text,
        "type": new_type,
        "choices": str([s.strip() for s in new_opts.split(",")])
        if new_type == "mc"
        else "",
        "answer": new_ans,
        "image_url": image_url,
    }

    df = df._append(new_row, ignore_index=True)
    tabs[vak] = df

    if save_excel_to_github(tabs):
        st.cache_data.clear()
        st.success("Nieuwe vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
    else:
        st.error("❌ Fout bij uploaden van Excel.")
