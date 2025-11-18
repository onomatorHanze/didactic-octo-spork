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
FILE_PATH = st.secrets["FILE_PATH"]        # bv. "data/quizvragen.xlsx"

IMAGE_DIR = "data/images"                  # map in repo voor afbeeldingen
EXCEL_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# ============================================================
# 🖼 Veilige image-viewer
# ============================================================
def safe_show_image(url: str, width: int = 300):
    """Toon afbeelding zonder Streamlit crash."""
    if not url or not isinstance(url, str):
        st.caption("Geen afbeelding gekoppeld.")
        return

    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            st.image(resp.content, width=width)
        else:
            st.caption("⚠️ Afbeelding niet beschikbaar.")
    except:
        st.caption("⚠️ Afbeelding niet te laden.")


# ============================================================
# 📥 Excel ophalen via GitHub API (NIET via RAW URL!)
# ============================================================
def load_excel_fresh() -> dict:
    """Altijd de nieuwste Excel ophalen via GitHub API (nooit caching)."""
    r = requests.get(EXCEL_API_URL, headers={"Authorization": f"token {TOKEN}"})
    data = r.json()

    content = base64.b64decode(data["content"])
    excel_bytes = io.BytesIO(content)

    tabs = pd.read_excel(excel_bytes, sheet_name=None, engine="openpyxl")

    # Zorg dat elke sheet image_url heeft + altijd str is
    for name, df in tabs.items():
        if "image_url" not in df.columns:
            df["image_url"] = ""
        df["image_url"] = df["image_url"].astype(str)
        tabs[name] = df

    return tabs


# ============================================================
# 📤 Excel opslaan naar GitHub
# ============================================================
def save_excel_to_github(tabs: dict) -> bool:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet, df in tabs.items():
            df.to_excel(writer, sheet_name=sheet, index=False)

    encoded_content = base64.b64encode(buf.getvalue()).decode()

    meta = requests.get(EXCEL_API_URL,
                        headers={"Authorization": f"token {TOKEN}"}).json()

    payload = {
        "message": "DocQuiz Admin – update vragenbestand",
        "content": encoded_content,
        "sha": meta.get("sha")
    }

    r = requests.put(EXCEL_API_URL,
                     headers={"Authorization": f"token {TOKEN}"},
                     data=json.dumps(payload))

    return r.status_code in (200, 201)


# ============================================================
# 🖼 Afbeelding uploaden
# ============================================================
def upload_image_to_github(file_bytes: bytes, filename: str) -> str | None:
    image_path = f"{IMAGE_DIR}/{filename}"
    api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    meta = requests.get(api_url, headers={"Authorization": f"token {TOKEN}"}).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode()
    payload = {"message": f"Upload afbeelding {filename}", "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(api_url,
                     headers={"Authorization": f"token {TOKEN}"},
                     data=json.dumps(payload))

    if r.status_code not in (200, 201):
        st.error(f"❌ Uploaden mislukt (status {r.status_code})")
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{image_path}"


# ============================================================
# 🧠 Session state
# ============================================================
if "edit_idx" not in st.session_state:
    st.session_state.edit_idx = None

if "delete_idx" not in st.session_state:
    st.session_state.delete_idx = None


# ============================================================
# 📚 Excel ophalen (altijd vers)
# ============================================================
tabs = load_excel_fresh()


# ============================================================
# 📘 Vak kiezen
# ============================================================
st.subheader("📘 Kies een vak")
vak = st.selectbox("Vak", list(tabs.keys()))
df = tabs[vak]


# ============================================================
# 📄 Alle vragen
# ============================================================
st.subheader("📄 Alle vragen")

for idx, row in df.iterrows():
    col1, col2, col3, col4 = st.columns([6, 1, 1, 1])

    with col1:
        txt = str(row["text"])
        st.write(f"**{idx} — {txt}**")

    with col2:
        if row.get("image_url"):
            st.caption("🖼")

    with col3:
        if st.button("✏️", key=f"edit_btn_{vak}_{idx}"):
            st.session_state.edit_idx = idx
            st.rerun()

    with col4:
        if st.button("❌", key=f"del_btn_{vak}_{idx}"):
            st.session_state.delete_idx = idx
            st.rerun()


# ============================================================
# 🗑️ Verwijderen
# ============================================================
if st.session_state.delete_idx is not None:
    idx = st.session_state.delete_idx

    st.markdown("---")
    st.subheader("❗ Weet je zeker dat je deze vraag wilt verwijderen?")
    st.write(f"**{idx} — {df.loc[idx, 'text']}**")

    colA, colB = st.columns([1, 1])
    with colA:
        if st.button("✔ Ja verwijderen"):
            df = df.drop(idx).reset_index(drop=True)
            tabs[vak] = df

            if save_excel_to_github(tabs):
                st.success("Vraag verwijderd!")
                time.sleep(1)
                st.session_state.delete_idx = None
                st.rerun()

    with colB:
        if st.button("✖ Annuleer"):
            st.session_state.delete_idx = None
            st.rerun()


# ============================================================
# ✏️ Bewerken
# ============================================================
if st.session_state.edit_idx is not None:
    idx = st.session_state.edit_idx
    vraag = df.loc[idx]

    st.markdown("---")
    st.subheader(f"✏️ Vraag {idx} bewerken")

    with st.container(border=True):
        # Basisvelden
        edit_text = st.text_input("Vraag", vraag["text"], key=f"edit_text_{idx}")
        edit_type = st.selectbox(
            "Type",
            ["mc", "tf", "input"],
            index=["mc", "tf", "input"].index(vraag["type"]),
            key=f"edit_type_{idx}",
        )

        # Afbeelding
        st.markdown("#### Afbeelding")
        safe_show_image(vraag.get("image_url", ""))

        new_img = st.file_uploader(
            "Nieuwe afbeelding (optioneel)",
            type=["png", "jpg", "jpeg"],
            key=f"edit_img_{idx}",
        )
        remove_img = st.checkbox(
            "Afbeelding verwijderen",
            key=f"edit_remove_{idx}",
        )

        # Type velden
        if edit_type == "mc":
            raw = vraag["choices"]
            opts = ast.literal_eval(raw) if raw else []
            new_opts = st.text_input(
                "MC-opties (komma gescheiden)",
                ", ".join(opts),
                key=f"opts_{idx}",
            )
            new_ans = st.number_input(
                "Index juiste antwoord",
                value=int(vraag["answer"]),
                min_value=0,
                key=f"ans_{idx}",
            )

        elif edit_type == "tf":
            new_opts = ""
            new_ans = st.selectbox(
                "Correct?",
                [True, False],
                index=0 if vraag["answer"] else 1,
                key=f"ans_tf_{idx}",
            )

        else:
            new_opts = ""
            new_ans = st.text_input(
                "Correct antwoord",
                str(vraag["answer"]),
                key=f"ans_inp_{idx}",
            )

        # Opslaan
        if st.button("💾 Opslaan", key=f"save_{idx}"):
            df.loc[idx, "text"] = edit_text
            df.loc[idx, "type"] = edit_type

            if edit_type == "mc":
                df.loc[idx, "choices"] = str([s.strip() for s in new_opts.split(",")])
            else:
                df.loc[idx, "choices"] = ""

            df.loc[idx, "answer"] = new_ans

            # Afbeelding verwerken
            if remove_img:
                df.loc[idx, "image_url"] = ""

            elif new_img:
                ext = new_img.name.split(".")[-1]
                filename = f"{vak}_q{idx}_{int(time.time())}.{ext}"
                uploaded = upload_image_to_github(new_img.read(), filename)
                if uploaded:
                    df.loc[idx, "image_url"] = uploaded

            tabs[vak] = df

            if save_excel_to_github(tabs):
                st.success("Opgeslagen!")
                time.sleep(1)
                st.session_state.edit_idx = None
                st.rerun()

        if st.button("❌ Annuleer", key=f"cancel_{idx}"):
            st.session_state.edit_idx = None
            st.rerun()


# ============================================================
# ➕ Nieuwe vraag
# ============================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag toevoegen")

new_text = st.text_input("Vraagtekst", key="new_text")
new_type = st.selectbox("Type", ["mc", "tf", "input"], key="new_type")

if new_type == "mc":
    new_opts = st.text_input("MC-opties (komma gescheiden)", key="new_opts")
    new_ans = st.number_input("Index juiste antwoord", min_value=0, key="new_ans_mc")
elif new_type == "tf":
    new_opts = ""
    new_ans = st.selectbox("Correct?", [True, False], key="new_ans_tf")
else:
    new_opts = ""
    new_ans = st.text_input("Correct antwoord", key="new_ans_input")

new_img = st.file_uploader("Afbeelding", type=["png", "jpg", "jpeg"], key="new_img")

if st.button("➕ Toevoegen", key="add_new"):
    if not new_text.strip():
        st.error("❌ Vraagtekst mag niet leeg zijn.")
        st.stop()

    # Afbeelding uploaden (optioneel)
    img_url = ""
    if new_img:
        ext = new_img.name.split(".")[-1]
        filename = f"{vak}_new_{int(time.time())}.{ext}"
        uploaded = upload_image_to_github(new_img.read(), filename)
        if uploaded:
            img_url = uploaded

    # MC-opties verwerken
    if new_type == "mc":
        opts_list = [s.strip() for s in new_opts.split(",") if s.strip()]
        choices_val = str(opts_list)
    else:
        choices_val = ""

    # Nieuwe rij aanmaken
    new_row = {
        "text": new_text,
        "type": new_type,
        "choices": choices_val,
        "answer": new_ans,
        "image_url": img_url,
    }

    df = df._append(new_row, ignore_index=True)
    tabs[vak] = df

    if save_excel_to_github(tabs):
        st.success("Nieuwe vraag toegevoegd!")
        time.sleep(1)
        st.rerun()
