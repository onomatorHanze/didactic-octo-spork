import streamlit as st
import pandas as pd
import requests
import base64
import json
import time
import os

TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
FILE_PATH = st.secrets["FILE_PATH"]

RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Voeg nieuwe vragen toe")

@st.cache_data
def load_excel():
    df_dict = pd.read_excel(RAW_URL, sheet_name=None, engine="openpyxl")
    return df_dict

def upload_to_github(updated_excel_bytes):
    encoded = base64.b64encode(updated_excel_bytes).decode()

    meta = requests.get(API_URL, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta["sha"]

    data = {
        "message": "Nieuwe quizvraag toegevoegd via Streamlit Admin",
        "content": encoded,
        "sha": sha
    }

    r = requests.put(API_URL,
                     headers={"Authorization": f"token {TOKEN}"},
                     data=json.dumps(data))
    return r.status_code == 200

tabs = load_excel()
st.subheader("📚 Kies vak / tabblad")
vak = st.selectbox("Vak", list(tabs.keys()))


# --------------------------------------------------------
# Overzicht van alle vragen in het gekozen vak
# --------------------------------------------------------
st.subheader("📄 Huidige vragen in dit vak")

df_preview = tabs[vak]  # DataFrame van het gekozen tabblad

# Mooiere kolomnamen (optioneel)
show_df = df_preview.rename(columns={
    "text": "Vraag",
    "type": "Type",
    "choices": "Opties",
    "answer": "Antwoord",
    "tags": "Tags" if "tags" in df_preview.columns else "Tags"
})

st.dataframe(
    show_df,
    use_container_width=True,
    hide_index=True
)

st.subheader("✏️ Nieuwe vraag toevoegen")

st.subheader("📄 Huidige vragen in dit vak")




q_text = st.text_input("Vraagtekst")
q_type = st.selectbox("Vraagtype", ["mc", "tf", "input"])

if q_type == "mc":
    mc_opties = st.text_input("Meerkeuze-opties (komma gescheiden)")
    mc_answer = st.number_input("Index juiste antwoord (0 = eerste)", 0)
elif q_type == "tf":
    mc_opties = ""
    mc_answer = st.selectbox("Correct?", [True, False])
else:
    mc_opties = ""
    mc_answer = st.text_input("Correct antwoord")

if st.button("➕ Voeg vraag toe"):
    if q_text.strip() == "":
        st.error("❌ Je moet een vraag invullen")
        st.stop()

    df = tabs[vak]

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
        st.success("✅ Vraag toegevoegd en naar GitHub geüpload!")
        time.sleep(1)
        st.rerun()
    else:
        st.error("❌ Upload naar GitHub mislukt!")
