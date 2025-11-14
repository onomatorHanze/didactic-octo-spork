import streamlit as st
import pandas as pd
import requests
import base64
import json
import time

# Streamlit secrets ophalen
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
FILE_PATH = st.secrets["FILE_PATH"]

RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")

# --------------------------------------------------------
# Excel laden
# --------------------------------------------------------
@st.cache_data
def load_excel():
    return pd.read_excel(RAW_URL, sheet_name=None, engine="openpyxl")


def upload_to_github(updated_excel_bytes):
    encoded = base64.b64encode(updated_excel_bytes).decode()
    meta = requests.get(API_URL, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta["sha"]

    payload = {
        "message": "Quizvragen aangepast via Admin",
        "content": encoded,
        "sha": sha
    }

    response = requests.put(
        API_URL, 
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload)
    )
    return response.status_code == 200


# --------------------------------------------------------
# Kies vak (tabblad)
# --------------------------------------------------------
tabs = load_excel()

st.subheader("📚 Kies vak / tabblad")
vak = st.selectbox("Vak", list(tabs.keys()), key="select_vak")

df = tabs[vak]

# --------------------------------------------------------
# Overzicht vragen + Delete-knoppen
# --------------------------------------------------------
st.subheader("📄 Alle vragen in dit vak")

for index, row in df.iterrows():
    col1, col2, col3 = st.columns([6, 2, 1])

    with col1:
        st.write(f"**{index} – {row['text']}**")

    with col2:
        st.caption(f"Type: {row['type']}")

    with col3:
        if st.button("❌", key=f"overview_del_{index}"):
            df = df.drop(index).reset_index(drop=True)
            tabs[vak] = df

            # Excel opslaan
            with pd.ExcelWriter("temp.xlsx", engine="openpyxl") as writer:
                for s, content in tabs.items():
                    content.to_excel(writer, sheet_name=s, index=False)

            with open("temp.xlsx", "rb") as f:
                excel_bytes = f.read()

            if upload_to_github(excel_bytes):
                st.success(f"Vraag {index} verwijderd!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Fout bij upload naar GitHub!")


# --------------------------------------------------------
# Vraag bewerken (inclusief verwijderen)
# --------------------------------------------------------
st.subheader("✏️ Vraag bewerken of verwijderen")

edit_index = st.selectbox(
    "Welke vraag wil je bewerken of verwijderen?",
    options=list(df.index),
    format_func=lambda x: f"{x} – {df.loc[x, 'text']}",
    key="edit_select"
)

if edit_index is not None:
    vraag = df.loc[edit_index]

    st.write("### ✏️ Bewerk vraag:")

    edit_text = st.text_input("Vraagtekst:", vraag["text"], key="edit_text")
    edit_type = st.selectbox(
        "Vraagtype:",
        ["mc", "tf", "input"],
        index=["mc", "tf", "input"].index(vraag["type"]),
        key="edit_type"
    )

    # Type-afhankelijke velden
    if edit_type == "mc":
        bestaande = eval(vraag["choices"]) if isinstance(vraag["choices"], str) else []
        edit_choices = st.text_input("Meerkeuze-opties (komma gescheiden):", ", ".join(bestaande), key="edit_choices")
        edit_answer = st.number_input("Index juiste antwoord:", value=int(vraag["answer"]), min_value=0, key="edit_answer")
    elif edit_type == "tf":
        edit_choices = ""
        edit_answer = st.selectbox("Correct?", [True, False], index=0 if vraag["answer"] else 1, key="edit_tf")
    else:
        edit_choices = ""
        edit_answer = st.text_input("Correct antwoord:", str(vraag["answer"]), key="edit_input")

    col_save, col_delete = st.columns(2)

    # Opslaan wijzigingen
    with col_save:
        if st.button("💾 Opslaan wijzigingen", key="save_btn"):
            df.loc[edit_index, "text"] = edit_text
            df.loc[edit_index, "type"] = edit_type
            df.loc[edit_index, "choices"] = str(edit_choices.split(",")) if edit_type == "mc" else ""
            df.loc[edit_index, "answer"] = edit_answer
            tabs[vak] = df

            # Excel opslaan
            with pd.ExcelWriter("temp.xlsx", engine="openpyxl") as writer:
                for s, content in tabs.items():
                    content.to_excel(writer, sheet_name=s, index=False)

            with open("temp.xlsx", "rb") as f:
                excel_bytes = f.read()

            if upload_to_github(excel_bytes):
                st.success("✅ Vraag succesvol bijgewerkt!")
                time.sleep(1)
                st.rerun()

    # Verwijderen knop
    with col_delete:
        if st.button("🗑️ Verwijder deze vraag", key="delete_btn"):
            df = df.drop(edit_index).reset_index(drop=True)
            tabs[vak] = df

            # Excel wegschrijven
            with pd.ExcelWriter("temp.xlsx", engine="openpyxl") as writer:
                for s, content in tabs.items():
                    content.to_excel(writer, sheet_name=s, index=False)

            with open("temp.xlsx", "rb") as f:
                excel_bytes = f.read()

            if upload_to_github(excel_bytes):
                st.success("🗑️ Vraag verwijderd!")
                time.sleep(1)
                st.rerun()


# --------------------------------------------------------
# Nieuwe vraag toevoegen
# --------------------------------------------------------
st.subheader("➕ Nieuwe vraag toevoegen")

q_text = st.text_input("Vraagtekst:", key="new_text")
q_type = st.selectbox("Vraagtype:", ["mc", "tf", "input"], key="new_type")

if q_type == "mc":
    mc_opties = st.text_input("Meerkeuze-opties (komma gescheiden):", key="new_choices")
    mc_answer = st.number_input("Index juiste antwoord:", min_value=0, key="new_answer")
elif q_type == "tf":
    mc_opties = ""
    mc_answer = st.selectbox("Correct?", [True, False], key="new_tf")
else:
    mc_opties = ""
    mc_answer = st.text_input("Correct antwoord:", key="new_input")

if st.button("➕ Voeg toe", key="add_btn"):
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
        st.success("✅ Vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
