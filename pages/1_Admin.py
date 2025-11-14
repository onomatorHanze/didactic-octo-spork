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

IMAGE_DIR = "data/images"                # map in repo voor afbeeldingen

RAW_EXCEL_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
EXCEL_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# ============================================================
# 🖼 Veilige image-viewer
# ============================================================
def safe_show_image(url: str, width: int = 350):
    """Toon een afbeelding zónder Streamlit te laten crashen."""
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
# 📥 Excel inlezen
# ============================================================
@st.cache_data
def load_excel() -> dict:
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

    encoded = base64.b64encode(buf.getvalue()).decode()

    meta = requests.get(
        EXCEL_API_URL,
        headers={"Authorization": f"token {TOKEN}"}
    ).json()

    payload = {
        "message": "Update quizvragen via Admin",
        "content": encoded,
        "sha": meta.get("sha"),  # mag None zijn: GitHub maakt dan een nieuw bestand
    }

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json"
    }


    if r.status_code not in (200, 201):
        st.error(f"❌ Excel upload mislukt (status {r.status_code}).")
        try:
            st.code(r.text, language="json")
        except Exception:
            pass
        return False

    return True


# ============================================================
# 🖼 Afbeelding uploaden naar GitHub
# ============================================================
def upload_image_to_github(file_bytes: bytes, filename: str) -> str | None:
    """Upload een afbeelding naar data/images/<filename> in de repo."""
    image_path = f"{IMAGE_DIR}/{filename}"
    image_api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    # Kijken of hij al bestaat (dan SHA meesturen)
    meta = requests.get(
        image_api_url,
        headers={"Authorization": f"token {TOKEN}"}
    ).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode()
    payload = {
        "message": f"Upload image {filename}",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json"
    }

    r = requests.put(image_api_url, headers=headers, data=json.dumps(payload))

    if r.status_code not in (200, 201):
        st.error(f"❌ Upload van afbeelding mislukt (status {r.status_code}).")
        try:
            st.code(r.text, language="json")
        except Exception:
            pass
        return None

    # Raw URL teruggeven
    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{image_path}"


# ============================================================
# 🧠 Session state
# ============================================================
if "edit_index" not in st.session_state:
    st.session_state["edit_index"] = None

if "confirm_delete_index" not in st.session_state:
    st.session_state["confirm_delete_index"] = None


# ============================================================
# 📚 Vakken laden
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
        txt_full = str(row.get("text", ""))
        txt_short = txt_full[:80] + ("…" if len(txt_full) > 80 else "")
        st.write(f"**{idx} – {txt_short}**")

    with col2:
        if isinstance(row.get("image_url"), str) and row["image_url"].strip():
            st.caption("🖼")

    with col3:
        if st.button("✏️", key=f"edit_{vak}_{idx}"):
            st.session_state["edit_index"] = idx
            st.session_state["confirm_delete_index"] = None
            st.rerun()

    with col4:
        if st.button("❌", key=f"del_{vak}_{idx}"):
            st.session_state["confirm_delete_index"] = idx
            st.session_state["edit_index"] = None
            st.rerun()


# ============================================================
# 🗑️ Verwijderen (met bevestiging)
# ============================================================
if st.session_state["confirm_delete_index"] is not None:
    del_idx = st.session_state["confirm_delete_index"]

    st.markdown("---")
    st.subheader("❓ Deze vraag verwijderen?")
    st.write(f"**{del_idx} – {df.loc[del_idx, 'text']}**")

    c1, c2 = st.columns([1, 1])

    with c1:
        if st.button("✔ Verwijderen", key="delete_yes"):
            df = df.drop(del_idx).reset_index(drop=True)
            tabs[vak] = df

            if save_excel_to_github(tabs):
                st.cache_data.clear()
                st.success("Vraag verwijderd!")
                time.sleep(1)
                st.session_state["confirm_delete_index"] = None
                st.rerun()

    with c2:
        if st.button("✖ Annuleer", key="delete_no"):
            st.session_state["confirm_delete_index"] = None
            st.rerun()


# ============================================================
# ✏️ Bewerken
# ============================================================
if st.session_state["edit_index"] is not None:
    idx = st.session_state["edit_index"]
    vraag = df.loc[idx]

    st.markdown("---")
    st.subheader(f"✏️ Vraag {idx} bewerken")

    with st.container(border=True):

        edit_text = st.text_input(
            "Vraagtekst",
            value=str(vraag.get("text", "")),
            key=f"edit_text_{idx}",
        )

        type_list = ["mc", "tf", "input"]
        current_type = vraag.get("type", "mc")
        if current_type not in type_list:
            current_type = "mc"

        edit_type = st.selectbox(
            "Vraagtype",
            type_list,
            index=type_list.index(current_type),
            key=f"edit_type_{idx}",
        )

        # ---------------- Afbeelding ----------------
        st.markdown("#### Afbeelding")
        safe_show_image(vraag.get("image_url", ""))

        new_img = st.file_uploader(
            "Nieuwe afbeelding uploaden (optioneel)",
            type=["png", "jpg", "jpeg"],
            key=f"edit_img_{idx}",
        )
        remove_img = st.checkbox(
            "Afbeelding verwijderen",
            key=f"edit_remove_{idx}",
        )

        # ---------------- Type-specifieke velden -------------
        if edit_type == "mc":
            raw_choices = str(vraag.get("choices", ""))
            opts = []
            if raw_choices.strip():
                try:
                    parsed = ast.literal_eval(raw_choices)
                    if isinstance(parsed, (list, tuple)):
                        opts = [str(x) for x in parsed]
                except Exception:
                    opts = []

            new_opts = st.text_input(
                "MC-opties (komma gescheiden)",
                ", ".join(opts),
                key=f"edit_opts_{idx}",
            )
            new_ans = st.number_input(
                "Index juiste antwoord (0 = eerste)",
                min_value=0,
                value=int(vraag.get("answer", 0)),
                key=f"edit_ans_{idx}",
            )

        elif edit_type == "tf":
            new_opts = ""
            new_ans = st.selectbox(
                "Correct?",
                [True, False],
                index=0 if bool(vraag.get("answer", True)) else 1,
                key=f"edit_tf_{idx}",
            )

        else:  # input
            new_opts = ""
            new_ans = st.text_input(
                "Correct antwoord",
                value=str(vraag.get("answer", "")),
                key=f"edit_inp_{idx}",
            )

        c1, c2 = st.columns([2, 1])

        with c1:
            if st.button("💾 Opslaan", key=f"edit_save_{idx}"):

                df.loc[idx, "text"] = edit_text
                df.loc[idx, "type"] = edit_type
                df.loc[idx, "choices"] = (
                    str([s.strip() for s in new_opts.split(",")])
                    if edit_type == "mc"
                    else ""
                )
                df.loc[idx, "answer"] = new_ans

                # Afbeelding verwerken
                if "image_url" not in df.columns:
                    df["image_url"] = ""

                if remove_img:
                    # Alleen de URL leegmaken – bestand zelf laten staan
                    df.loc[idx, "image_url"] = ""
                elif new_img is not None:
                    ext = new_img.name.split(".")[-1].lower()
                    if ext not in ("png", "jpg", "jpeg"):
                        st.error("❌ Ongeldig afbeeldingsformaat.")
                    else:
                        safe_vak = vak.replace(" ", "_")
                        filename = f"{safe_vak}_edit_{idx}_{int(time.time())}.{ext}"
                        uploaded = upload_image_to_github(new_img.read(), filename)
                        if uploaded:
                            df.loc[idx, "image_url"] = uploaded

                tabs[vak] = df

                if save_excel_to_github(tabs):
                    st.cache_data.clear()
                    st.success("Vraag bijgewerkt!")
                    time.sleep(1)
                    st.session_state["edit_index"] = None
                    st.rerun()

        with c2:
            if st.button("✖ Annuleer", key=f"edit_cancel_{idx}"):
                st.session_state["edit_index"] = None
                st.rerun()


# ============================================================
# ➕ Nieuwe vraag
# ============================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag toevoegen")

new_text = st.text_input("Vraagtekst:", key="new_q_text")
new_type = st.selectbox("Type:", ["mc", "tf", "input"], key="new_q_type")

if new_type == "mc":
    new_opts = st.text_input(
        "MC-opties (komma gescheiden):",
        key="new_q_opts",
    )
    new_ans = st.number_input(
        "Index juiste antwoord (0 = eerste)",
        min_value=0,
        step=1,
        key="new_q_ans_mc",
    )
elif new_type == "tf":
    new_opts = ""
    new_ans = st.selectbox(
        "Correct?",
        [True, False],
        key="new_q_ans_tf",
    )
else:
    new_opts = ""
    new_ans = st.text_input(
        "Correct antwoord:",
        key="new_q_ans_input",
    )

new_img = st.file_uploader(
    "Afbeelding uploaden (optioneel)",
    type=["png", "jpg", "jpeg"],
    key="new_q_img",
)

if st.button("➕ Toevoegen", key="new_q_add_btn"):

    if new_text.strip() == "":
        st.error("❌ Vraagtekst mag niet leeg zijn.")
        st.stop()

    # Afbeelding uploaden
    img_url = ""
    if new_img is not None:
        ext = new_img.name.split(".")[-1].lower()
        if ext not in ("png", "jpg", "jpeg"):
            st.error("❌ Ongeldig afbeeldingsformaat.")
            st.stop()
        safe_vak = vak.replace(" ", "_")
        filename = f"{safe_vak}_new_{int(time.time())}.{ext}"
        uploaded = upload_image_to_github(new_img.read(), filename)
        if uploaded:
            img_url = uploaded

    # MC-opties netjes opslaan
    if new_type == "mc":
        opts_clean = [s.strip() for s in new_opts.split(",") if s.strip()]
        choices_val = str(opts_clean)
    else:
        choices_val = ""

    # Zorg dat alle kolommen gevuld worden (ook topic, tags, enz.)
    base_row = {col: "" for col in df.columns}
    base_row.update({
        "text": new_text,
        "type": new_type,
        "choices": choices_val,
        "answer": new_ans,
        "image_url": img_url,
    })

    df = df._append(base_row, ignore_index=True)
    tabs[vak] = df

    if save_excel_to_github(tabs):
        st.cache_data.clear()
        st.success("Nieuwe vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
