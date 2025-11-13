import streamlit as st
import pandas as pd
import requests
import base64
import json
import time
import os

# Streamlit Secrets
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
FILE_PATH = st.secrets["FILE_PATH"]

RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Voeg nieuwe vragen toe")


# --------------------------------------------------------
# Download bestaand Excel bestand
# --------------------------------------------------------
@st.cache_data
def load_excel():
    df_dict = pd.read_excel(RAW_URL, sheet_name=None, engine="openpyxl")
    return df_dict


# --------------------------------------------------------
# Upload nieuwe versie naar GitHub
# --------------------------------------------------------
def upload_to_github(updated_excel_bytes):
    # Base64 encode
    encoded = base64.b64encode(updated_excel_bytes).decode()

    # Bestaat file? -> SHA ophalen
    meta = requests.get(API_URL, headers={"Authorization": f"token {TOKEN}"})
    sha = meta.json()["sha"]

    commit_message = "Nieuwe quizvraag toegevoegd via Streamlit Admin"

    data = {
        "message": commit_message,
        "content": encoded,
        "sha": sha
    }

    response = requests.put(API_URL,
                            headers={"Authorization": f"token {TOKEN}"},
                            data=json.dumps(data))

    return response.status_code == 200


# --------------------------------------------------------
# Admin UI
# --------------------------------------------------------
tabs = load_excel()
st.subheader("📚 Kies vak / tabblad")
vak = st.selectbox("Vak", list(tabs.keys()))


# --------------------------------------------------------
# Vraag invoeren
# --------------------------------------------------------
st.subheader("✏️ Nieuwe vraag hinzufügen")

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

    # Excel opnieuw opslaan naar bytes
    buffer = pd.ExcelWriter("temp.xlsx", engine="openpyxl")
    for sheet, content in tabs.items():
        content.to_excel(buffer, sheet_name=sheet, index=False)
    buffer.close()

    with open("temp.xlsx", "rb") as f:
        excel_bytes = f.read()

    ok = upload_to_github(excel_bytes)

    if ok:
        st.success("✅ Vraag toegevoegd en naar GitHub geüpload!")
        time.sleep(1)
        st.rerun()
    else:
        st.error("❌ Upload naar GitHub mislukt!")
