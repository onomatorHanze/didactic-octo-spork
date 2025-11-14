import streamlit as st
import pandas as pd
import requests
import base64
import json
import time


# --- Secrets ---
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
FILE_PATH = st.secrets["FILE_PATH"]

RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# --- Excel laden ---
@st.cache_data
def load_excel():
    return pd.read_excel(RAW_URL, sheet_name=None, engine="openpyxl")


def upload_to_github(updated_excel_bytes):
    encoded = base64.b64encode(updated_excel_bytes).decode()
    meta = requests.get(API_URL, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta["sha"]

    payload = {"message": "Quizvragen aangepast via Admin", "content": encoded, "sha": sha}

    response = requests.put(
        API_URL,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload)
    )
    return response.status_code == 200


# --- UI STATE ---
if "edit_mode" not in st.session_state:
    st.session_state["edit_mode"] = None

if "delete_confirm" not in st.session_state:
    st.session_state["delete_confirm"] = None


# --- Kies tabblad ---
tabs = load_excel()

st.subheader("📚 Kies vak / tabblad")
vak = st.selectbox("Vak", list(tabs.keys()), key="select_vak")

df = tabs[vak]


# =====================================================================
# 📄 OVERZICHT VRAGEN – met bewerken & verwijderen knoppen
# =====================================================================
st.subheader("📄 Alle vragen in dit vak")

for index, row in df.iterrows():
    col1, col2, col3 = st.columns([6, 1.5, 1.5])

    with col1:
        st.write(f"**{index} – {row['text']}**")

    with col2:
        if st.button("✏️", key=f"edit_{index}"):
            st.session_state["edit_mode"] = index
            st.rerun()

    with col3:
        if st.button("❌", key=f"delete_{index}"):
            st.session_state["delete_confirm"] = index
            st.rerun()


# =====================================================================
# 🗑️ POPUP — VERWIJDER BEVESTIGING
# =====================================================================
if st.session_state["delete_confirm"] is not None:

    delete_index = st.session_state["delete_confirm"]
    vraag = df.loc[delete_index]["text"]

    st.markdown("---")
    st.markdown(f"### ❓ Weet je zeker dat je deze vraag wilt verwijderen?")
    st.markdown(f"**{delete_index} – {vraag}**")

    with st.container(border=True):

        colA, colB = st.columns([1, 1])

        with colA:
            if st.button("✔ Ja, verwijderen", key="confirm_delete"):
                df = df.drop(delete_index).reset_index(drop=True)
                tabs[vak] = df

                # Wegschrijven
                with pd.ExcelWriter("temp.xlsx", engine="openpyxl") as writer:
                    for sheet, content in tabs.items():
                        content.to_excel(writer, sheet_name=sheet, index=False)

                with open("temp.xlsx", "rb") as f:
                    excel_bytes = f.read()

                if upload_to_github(excel_bytes):
                    st.success(f"Vraag {delete_index} verwijderd!")
                    time.sleep(1)
                    st.session_state["delete_confirm"] = None
                    st.rerun()

        with colB:
            if st.button("✖ Annuleer", key="cancel_delete"):
                st.session_state["delete_confirm"] = None
                st.rerun()


# =====================================================================
# ✏️ BEWERK MODAL
# =====================================================================
if st.session_state["edit_mode"] is not None:

    edit_index = st.session_state["edit_mode"]
    vraag = df.loc[edit_index]

    st.markdown("---")
    st.subheader(f"✏️ Vraag {edit_index} bewerken")

    with st.container(border=True):

        edit_text = st.text_input("Vraagtekst", value=vraag["text"], key="edit_text")
        edit_type = st.selectbox(
            "Vraagtype",
            ["mc", "tf", "input"],
            index=["mc", "tf", "input"].index(vraag["type"]),
            key="edit_type"
        )

        # --- Vraagtype-specifieke velden ---
        if edit_type == "mc":
            bestaande = eval(vraag["choices"]) if isinstance(vraag["choices"], str) else []
            edit_choices = st.text_input("MC-opties (comma gescheiden)", ", ".join(bestaande), key="edit_choices")
            edit_answer = st.number_input("Index juiste antwoord", min_value=0, value=int(vraag["answer"]), key="edit_answer")

        elif edit_type == "tf":
            edit_choices = ""
            edit_answer = st.selectbox("Correct?", [True, False], index=0 if vraag["answer"] else 1, key="edit_tf")

        else:
            edit_choices = ""
            edit_answer = st.text_input("Correct antwoord", str(vraag["answer"]), key="edit_inp")

        colA, colB = st.columns([2, 1])

        with colA:
            if st.button("💾 Opslaan wijzigingen", key="save_edit"):
                df.loc[edit_index, "text"] = edit_text
                df.loc[edit_index, "type"] = edit_type
                df.loc[edit_index, "choices"] = str(edit_choices.split(",")) if edit_type == "mc" else ""
                df.loc[edit_index, "answer"] = edit_answer

                tabs[vak] = df

                # Wegschrijven
                with pd.ExcelWriter("temp.xlsx", engine="openpyxl") as writer:
                    for sheet, content in tabs.items():
                        content.to_excel(writer, sheet_name=sheet, index=False)

                with open("temp.xlsx", "rb") as f:
                    excel_bytes = f.read()

                if upload_to_github(excel_bytes):
                    st.success("Vraag bijgewerkt!")
                    time.sleep(1)
                    st.session_state["edit_mode"] = None
                    st.rerun()

        with colB:
            if st.button("❌ Annuleer", key="cancel_edit"):
                st.session_state["edit_mode"] = None
                st.rerun()


# =====================================================================
# ➕ NIEUWE VRAAG TOEVOEGEN
# =====================================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag toevoegen")

q_text = st.text_input("Vraagtekst:", key="new_text")
q_type = st.selectbox("Vraagtype:", ["mc", "tf", "input"], key="new_type")

if q_type == "mc":
    mc_opties = st.text_input("MC-opties (comma gescheiden):", key="new_choices")
    mc_answer = st.number_input("Index juiste antwoord:", min_value=0, key="new_answer")

elif q_type == "tf":
    mc_opties = ""
    mc_answer = st.selectbox("Correct?", [True, False], key="new_tf")

else:
    mc_opties = ""
    mc_answer = st.text_input("Correct antwoord:", key="new_input")


if st.button("➕ Voeg toe", key="add_new"):
    if q_text.strip() == "":
        st.error("❌ Vul eerst een vraag in.")
        st.stop()

    new_row = {
        "text": q_text,
        "type": q_type,
        "choices": str(mc_opties.split(",")) if q_type == "mc" else "",
        "answer": mc_answer
    }

    df = df._append(new_row, ignore_index=True)
    tabs[vak] = df

    with pd.ExcelWriter("temp.xlsx", engine="openpyxl") as writer:
        for sheet, content in tabs.items():
            content.to_excel(writer, sheet_name=sheet, index=False)

    with open("temp.xlsx", "rb") as f:
        excel_bytes = f.read()

    if upload_to_github(excel_bytes):
        st.success("Vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
