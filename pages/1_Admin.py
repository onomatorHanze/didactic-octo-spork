import streamlit as st
import pandas as pd
import requests
import base64
import json
import time
import io

# =========================
# GitHub / repo config via secrets
# =========================
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
FILE_PATH = st.secrets["FILE_PATH"]          # bijv. "data/quizvragen.xlsx"

# Afbeeldingen komen in deze map in de repo:
IMAGE_DIR = "data/images"

# URLs
RAW_EXCEL_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
EXCEL_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# =========================
# Helpers
# =========================
@st.cache_data
def load_excel():
    """
    Laad alle tabbladen uit de Excel in als dict {sheet_name: DataFrame}.
    Zorgt ervoor dat image_url, explanation en formula_latex altijd bestaan.
    """
    tabs = pd.read_excel(RAW_EXCEL_URL, sheet_name=None, engine="openpyxl")
    for name, df in tabs.items():
        if "image_url" not in df.columns:
            df["image_url"] = ""
        if "explanation" not in df.columns:
            df["explanation"] = ""
        if "formula_latex" not in df.columns:
            df["formula_latex"] = ""
        tabs[name] = df
    return tabs


def save_excel_to_github(tabs: dict) -> bool:
    """
    Schrijf alle sheets terug naar een Excel in memory
    en upload dat bestand naar GitHub via de contents-API.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in tabs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    excel_bytes = output.getvalue()

    encoded = base64.b64encode(excel_bytes).decode()

    meta = requests.get(
        EXCEL_API_URL,
        headers={"Authorization": f"token {TOKEN}"}
    ).json()
    sha = meta.get("sha")

    payload = {
        "message": "Quizvragen aangepast via Admin",
        "content": encoded,
        "sha": sha
    }

    response = requests.put(
        EXCEL_API_URL,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload)
    )
    return response.status_code in (200, 201)


def upload_image_to_github(file_bytes: bytes, filename: str) -> str | None:
    """
    Upload een afbeelding naar data/images/<filename> in de repo.
    Geeft de RAW URL terug of None bij fout.
    """
    image_path = f"{IMAGE_DIR}/{filename}"
    image_api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    # Check of bestand al bestaat (om eventueel te updaten)
    meta = requests.get(
        image_api_url,
        headers={"Authorization": f"token {TOKEN}"}
    ).json()
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

    if r.status_code in (200, 201):
        raw_url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{image_path}"
        return raw_url
    else:
        st.error("❌ Uploaden van afbeelding naar GitHub is mislukt.")
        return None


# =========================
# UI state
# =========================
if "edit_mode" not in st.session_state:
    st.session_state["edit_mode"] = None  # index van vraag die je bewerkt

if "delete_confirm" not in st.session_state:
    st.session_state["delete_confirm"] = None  # index die je wilt verwijderen


# =========================
# Excel inlezen en vak kiezen
# =========================
tabs = load_excel()

st.subheader("📚 Kies vak / tabblad")
vak = st.selectbox("Vak", list(tabs.keys()), key="select_vak")

df = tabs[vak]


# ============================================================
# 📄 OVERZICHT VRAGEN – met bewerken & verwijderen knoppen
# ============================================================
st.subheader("📄 Alle vragen in dit vak")

for index, row in df.iterrows():
    col1, col2, col3, col4 = st.columns([5, 1.5, 1.5, 2])

    with col1:
        text = str(row["text"])
        if len(text) > 80:
            text = text[:80] + "..."
        st.write(f"**{index} – {text}**")

    with col2:
        if isinstance(row.get("image_url"), str) and row["image_url"]:
            st.caption("🖼 Afbeelding")

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
# 🗑️ DELETE CONFIRM POPUP
# ============================================================
if st.session_state["delete_confirm"] is not None:
    delete_index = st.session_state["delete_confirm"]

    if delete_index < len(df):
        vraag = df.loc[delete_index, "text"]
        st.markdown("---")
        st.markdown("### ❓ Weet je zeker dat je deze vraag wilt verwijderen?")
        st.markdown(f"**{delete_index} – {vraag}**")

        with st.container(border=True):
            colA, colB = st.columns([1, 1])

            with colA:
                if st.button("✔ Ja, verwijderen", key="confirm_delete"):
                    df = df.drop(delete_index).reset_index(drop=True)
                    tabs[vak] = df

                    if save_excel_to_github(tabs):
                        st.cache_data.clear()
                        st.success(f"Vraag {delete_index} verwijderd!")
                        time.sleep(1)
                        st.session_state["delete_confirm"] = None
                        st.rerun()
                    else:
                        st.error("❌ Fout bij uploaden van Excel.")

            with colB:
                if st.button("✖ Annuleer", key="cancel_delete"):
                    st.session_state["delete_confirm"] = None
                    st.rerun()


# ============================================================
# ✏️ BEWERK MODAL
# ============================================================
if st.session_state["edit_mode"] is not None:
    edit_index = st.session_state["edit_mode"]

    if edit_index < len(df):
        vraag = df.loc[edit_index]

        st.markdown("---")
        st.subheader(f"✏️ Vraag {edit_index} bewerken")

        with st.container(border=True):
            # Basis velden
            edit_text = st.text_input("Vraagtekst", value=str(vraag["text"]), key="edit_text")

            edit_type = st.selectbox(
                "Vraagtype",
                ["mc", "tf", "input"],
                index=["mc", "tf", "input"].index(vraag["type"]),
                key="edit_type"
            )

            edit_expl = st.text_area(
                "Uitleg (optioneel)",
                value=str(vraag.get("explanation") or ""),
                key="edit_expl"
            )

            edit_formula = st.text_input(
                "LaTeX formule (optioneel)",
                value=str(vraag.get("formula_latex") or ""),
                key="edit_formula"
            )

            # Afbeelding: huidige + upload nieuwe
            st.markdown("#### Afbeelding")

            huidige_url = ""
            if "image_url" in df.columns and isinstance(vraag.get("image_url"), str):
                huidige_url = vraag.get("image_url") or ""

            if huidige_url:
                st.image(huidige_url, width=300)
            else:
                st.caption("Geen afbeelding gekoppeld.")

            image_file_edit = st.file_uploader(
                "Nieuwe afbeelding uploaden (optioneel)",
                type=["png", "jpg", "jpeg"],
                key="edit_img"
            )
            remove_img = st.checkbox("Afbeelding verwijderen", key="edit_remove_img")

            # Type-afhankelijke velden
            if edit_type == "mc":
                bestaande = []
                if isinstance(vraag["choices"], str) and vraag["choices"]:
                    try:
                        bestaande = eval(vraag["choices"])
                    except Exception:
                        bestaande = []
                edit_choices = st.text_input(
                    "MC-opties (komma gescheiden)",
                    ", ".join(bestaande),
                    key="edit_choices"
                )
                edit_answer = st.number_input(
                    "Index juiste antwoord",
                    min_value=0,
                    value=int(vraag["answer"]),
                    key="edit_answer"
                )

            elif edit_type == "tf":
                edit_choices = ""
                edit_answer = st.selectbox(
                    "Correct?",
                    [True, False],
                    index=0 if vraag["answer"] else 1,
                    key="edit_tf"
                )

            else:  # input
                edit_choices = ""
                edit_answer = st.text_input(
                    "Correct antwoord",
                    str(vraag["answer"]),
                    key="edit_ans_input"
                )

            colA, colB = st.columns([2, 1])

            with colA:
                if st.button("💾 Opslaan wijzigingen", key="save_edit"):
                    # Basisvelden
                    df.loc[edit_index, "text"] = edit_text
                    df.loc[edit_index, "type"] = edit_type
                    df.loc[edit_index, "choices"] = (
                        str(edit_choices.split(",")) if edit_type == "mc" else ""
                    )
                    df.loc[edit_index, "answer"] = edit_answer
                    df.loc[edit_index, "explanation"] = edit_expl
                    df.loc[edit_index, "formula_latex"] = edit_formula

                    # Zorg dat kolom bestaat
                    if "image_url" not in df.columns:
                        df["image_url"] = ""

                    # Afbeeldinglogica
                    if remove_img:
                        df.loc[edit_index, "image_url"] = ""
                    elif image_file_edit is not None:
                        ext = image_file_edit.name.split(".")[-1].lower()
                        if ext not in ("png", "jpg", "jpeg"):
                            st.error("❌ Ongeldig afbeeldingsformaat.")
                        else:
                            safe_vak = vak.replace(" ", "_")
                            filename = f"{safe_vak}_q{edit_index}_{int(time.time())}.{ext}"
                            file_bytes = image_file_edit.read()
                            new_url = upload_image_to_github(file_bytes, filename)
                            if new_url:
                                df.loc[edit_index, "image_url"] = new_url

                    tabs[vak] = df

                    if save_excel_to_github(tabs):
                        st.cache_data.clear()
                        st.success("✅ Vraag bijgewerkt!")
                        time.sleep(1)
                        st.session_state["edit_mode"] = None
                        st.rerun()
                    else:
                        st.error("❌ Fout bij uploaden van Excel.")

            with colB:
                if st.button("❌ Annuleer bewerken", key="cancel_edit"):
                    st.session_state["edit_mode"] = None
                    st.rerun()


# ============================================================
# ➕ NIEUWE VRAAG TOEVOEGEN
# ============================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag toevoegen")

q_text = st.text_input("Vraagtekst:", key="new_text")
q_type = st.selectbox("Vraagtype:", ["mc", "tf", "input"], key="new_type")
q_expl = st.text_area("Uitleg (optioneel):", key="new_expl")
q_formula = st.text_input("LaTeX formule (optioneel):", key="new_formula")

if q_type == "mc":
    mc_opties = st.text_input("MC-opties (komma gescheiden):", key="new_choices")
    mc_answer = st.number_input("Index juiste antwoord:", min_value=0, key="new_answer")
elif q_type == "tf":
    mc_opties = ""
    mc_answer = st.selectbox("Correct?", [True, False], key="new_tf")
else:
    mc_opties = ""
    mc_answer = st.text_input("Correct antwoord:", key="new_input")

image_file_new = st.file_uploader(
    "Afbeelding toevoegen (optioneel)", type=["png", "jpg", "jpeg"], key="new_img"
)

if st.button("➕ Voeg toe", key="add_new"):
    if q_text.strip() == "":
        st.error("❌ Vul eerst een vraag in.")
        st.stop()

    image_url = ""
    if image_file_new is not None:
        ext = image_file_new.name.split(".")[-1].lower()
        if ext not in ("png", "jpg", "jpeg"):
            st.error("❌ Ongeldig afbeeldingsformaat.")
        else:
            safe_vak = vak.replace(" ", "_")
            filename = f"{safe_vak}_new_{int(time.time())}.{ext}"
            file_bytes = image_file_new.read()
            new_url = upload_image_to_github(file_bytes, filename)
            if new_url:
                image_url = new_url

    new_row = {
        "text": q_text,
        "type": q_type,
        "choices": str(mc_opties.split(",")) if q_type == "mc" else "",
        "answer": mc_answer,
        "explanation": q_expl,
        "formula_latex": q_formula,
        "image_url": image_url
    }

    df = df._append(new_row, ignore_index=True)
    tabs[vak] = df

    if save_excel_to_github(tabs):
        st.cache_data.clear()
        st.success("✅ Nieuwe vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
    else:
        st.error("❌ Fout bij uploaden van Excel.")
st.markdown("---")
st.subheader("🔧 Debug: test afbeelding uploaden")

test_file = st.file_uploader("Test upload", type=["jpg", "png", "jpeg"], key="debug_test")

if test_file:
    st.write("▶ Proberen te uploaden...")

    filename = f"TEST_{int(time.time())}.jpg"
    image_path = f"{IMAGE_DIR}/{filename}"
    api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    encoded = base64.b64encode(test_file.read()).decode()

    payload = {
        "message": "DEBUG upload",
        "content": encoded
    }

    r = requests.put(
        api_url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload)
    )

    st.write("Status:", r.status_code)
    st.write("Response:", r.json())
