import streamlit as st
import requests
import base64
import json
import time

# ============================================================
# 🔧 GitHub-config (via Streamlit Secrets)
# ============================================================
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
FILE_PATH = st.secrets["FILE_PATH"]      # nu: "data/questions.json"

IMAGE_DIR = "data/images"

RAW_JSON_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{FILE_PATH}"
JSON_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# ============================================================
# Helpers
# ============================================================
@st.cache_data
def load_data() -> dict:
    """Lees de JSON met alle vragen in."""
    r = requests.get(RAW_JSON_URL, timeout=5)
    r.raise_for_status()
    data = r.json()

    # Veiligheid: structuur afdwingen
    if not isinstance(data, dict):
        data = {}

    for vak, vragen in list(data.items()):
        if not isinstance(vragen, list):
            data[vak] = []
            continue
        for q in vragen:
            if "image_url" not in q:
                q["image_url"] = ""

    return data


def save_data_to_github(data: dict, message: str) -> bool:
    """Schrijf de JSON terug naar GitHub."""
    content_str = json.dumps(data, ensure_ascii=False, indent=2)
    encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    meta = requests.get(
        JSON_API_URL,
        headers={"Authorization": f"token {TOKEN}"}
    ).json()
    sha = meta.get("sha")

    payload = {
        "message": message,
        "content": encoded,
        "sha": sha,
    }

    r = requests.put(
        JSON_API_URL,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )

    if r.status_code not in (200, 201):
        st.error(f"❌ Fout bij upload naar GitHub (status {r.status_code}).")
        try:
            st.code(r.text, language="json")
        except Exception:
            pass
        return False

    return True


def upload_image_to_github(file_bytes: bytes, filename: str) -> str | None:
    """Upload een afbeelding naar data/images/<filename> in de repo."""
    image_path = f"{IMAGE_DIR}/{filename}"
    image_api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{image_path}"

    # Bestaat al?
    meta = requests.get(
        image_api_url, headers={"Authorization": f"token {TOKEN}"}
    ).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode("utf-8")
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
        st.error(f"❌ Afbeelding upload mislukt (status {r.status_code}).")
        try:
            st.code(r.text, language="json")
        except Exception:
            pass
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{image_path}"


def safe_show_image(url: str, width: int = 350):
    """Afbeelding laten zien zonder crash."""
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
# Session state
# ============================================================
if "current_vak" not in st.session_state:
    st.session_state.current_vak = None
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "delete_index" not in st.session_state:
    st.session_state.delete_index = None


# ============================================================
# Data laden
# ============================================================
data = load_data()

if not data:
    st.info("Nog geen vragen-data gevonden in JSON.")
    st.stop()

vakken = sorted(data.keys())

st.subheader("📘 Kies een vak")
vak = st.selectbox("Vak", vakken, key="vak_select")

# Reset state als je van vak wisselt
if st.session_state.current_vak != vak:
    st.session_state.current_vak = vak
    st.session_state.edit_index = None
    st.session_state.delete_index = None

vragen = data.get(vak, [])


# ============================================================
# Overzicht
# ============================================================
st.subheader("📄 Alle vragen in dit vak")

if not vragen:
    st.info("Nog geen vragen voor dit vak.")
else:
    for idx, q in enumerate(vragen):
        col1, col2, col3, col4 = st.columns([5, 1, 1, 1])

        with col1:
            text = str(q.get("text", ""))
            kort = text[:80] + ("…" if len(text) > 80 else "")
            st.write(f"**{idx} – {kort}**")

        with col2:
            if isinstance(q.get("image_url"), str) and q["image_url"].strip():
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
# Verwijderen – bevestiging
# ============================================================
if st.session_state.delete_index is not None:
    del_idx = st.session_state.delete_index

    if 0 <= del_idx < len(vragen):
        st.markdown("---")
        st.subheader("❓ Deze vraag verwijderen?")
        st.write(f"**{del_idx} – {vragen[del_idx].get('text', '')}**")

        c1, c2 = st.columns([1, 1])

        with c1:
            if st.button("✔ Ja, verwijderen", key="delete_yes"):
                vragen.pop(del_idx)

                if save_data_to_github(data, f"Verwijder vraag {del_idx} in {vak}"):
                    st.cache_data.clear()
                    st.success("Vraag verwijderd.")
                    time.sleep(1)
                    st.session_state.delete_index = None
                    st.rerun()

        with c2:
            if st.button("✖ Nee, annuleren", key="delete_no"):
                st.session_state.delete_index = None
                st.rerun()


# ============================================================
# Bewerken
# ============================================================
if st.session_state.edit_index is not None:
    idx = st.session_state.edit_index

    if 0 <= idx < len(vragen):
        q = vragen[idx]

        st.markdown("---")
        st.subheader(f"✏️ Vraag {idx} bewerken")

        with st.container(border=True):
            # Basis
            edit_text = st.text_input(
                "Vraagtekst", value=str(q.get("text", "")), key=f"edit_text_{idx}"
            )

            type_opts = ["mc", "tf", "input"]
            current_type = q.get("type", "mc")
            if current_type not in type_opts:
                current_type = "mc"

            edit_type = st.selectbox(
                "Vraagtype",
                type_opts,
                index=type_opts.index(current_type),
                key=f"edit_type_{idx}",
            )

            # Afbeelding
            st.markdown("#### Afbeelding")
            safe_show_image(q.get("image_url", ""))

            new_img = st.file_uploader(
                "Nieuwe afbeelding uploaden (optioneel)",
                type=["png", "jpg", "jpeg"],
                key=f"edit_img_{idx}",
            )
            remove_img = st.checkbox(
                "Afbeelding verwijderen",
                key=f"edit_remove_{idx}",
            )

            # Type-specifiek
            if edit_type == "mc":
                raw_choices = q.get("choices", [])
                if not isinstance(raw_choices, list):
                    raw_choices = []
                default_choices_str = ", ".join(str(c) for c in raw_choices)
                choices_str = st.text_input(
                    "MC-opties (komma gescheiden)",
                    value=default_choices_str,
                    key=f"edit_opts_{idx}",
                )
                try:
                    default_answer = int(q.get("answer", 0))
                except Exception:
                    default_answer = 0
                edit_answer = st.number_input(
                    "Index juiste antwoord (0 = eerste)",
                    min_value=0,
                    value=default_answer,
                    step=1,
                    key=f"edit_ans_{idx}",
                )

            elif edit_type == "tf":
                choices_str = ""
                current_ans = bool(q.get("answer", True))
                edit_answer = st.selectbox(
                    "Correct?",
                    [True, False],
                    index=0 if current_ans else 1,
                    key=f"edit_tf_{idx}",
                )

            else:  # input
                choices_str = ""
                edit_answer = st.text_input(
                    "Correct antwoord",
                    value=str(q.get("answer", "")),
                    key=f"edit_inp_{idx}",
                )

            c1, c2 = st.columns([2, 1])

            with c1:
                if st.button("💾 Opslaan", key=f"save_{idx}"):
                    # Basisvelden
                    q["text"] = edit_text
                    q["type"] = edit_type

                    if edit_type == "mc":
                        opts_clean = [
                            s.strip()
                            for s in choices_str.split(",")
                            if s.strip()
                        ]
                        q["choices"] = opts_clean
                        q["answer"] = int(edit_answer)
                    elif edit_type == "tf":
                        q["choices"] = []
                        q["answer"] = bool(edit_answer)
                    else:
                        q["choices"] = []
                        q["answer"] = str(edit_answer)

                    # Afbeelding
                    if remove_img:
                        q["image_url"] = ""
                    elif new_img is not None:
                        ext = new_img.name.split(".")[-1].lower()
                        if ext not in ("png", "jpg", "jpeg"):
                            st.error("❌ Ongeldig afbeeldingsformaat.")
                        else:
                            safe_vak = vak.replace(" ", "_")
                            filename = f"{safe_vak}_q{idx}_{int(time.time())}.{ext}"
                            url = upload_image_to_github(new_img.read(), filename)
                            if url:
                                q["image_url"] = url

                    if save_data_to_github(data, f"Wijzig vraag {idx} in {vak}"):
                        st.cache_data.clear()
                        st.success("Vraag bijgewerkt.")
                        time.sleep(1)
                        st.session_state.edit_index = None
                        st.rerun()

            with c2:
                if st.button("✖ Annuleer", key=f"cancel_{idx}"):
                    st.session_state.edit_index = None
                    st.rerun()


# ============================================================
# Nieuwe vraag toevoegen
# ============================================================
st.markdown("---")
st.subheader("➕ Nieuwe vraag toevoegen")

new_text = st.text_input("Vraagtekst:", key="new_text")
new_type = st.selectbox("Type:", ["mc", "tf", "input"], key="new_type")

if new_type == "mc":
    new_opts_str = st.text_input(
        "MC-opties (komma gescheiden):", key="new_opts"
    )
    new_answer = st.number_input(
        "Index juiste antwoord (0 = eerste)",
        min_value=0,
        step=1,
        key="new_ans_mc",
    )
elif new_type == "tf":
    new_opts_str = ""
    new_answer = st.selectbox(
        "Correct?", [True, False], key="new_ans_tf"
    )
else:
    new_opts_str = ""
    new_answer = st.text_input(
        "Correct antwoord:", key="new_ans_input"
    )

new_img = st.file_uploader(
    "Afbeelding uploaden (optioneel)",
    type=["png", "jpg", "jpeg"],
    key="new_img",
)

if st.button("➕ Toevoegen", key="new_add_btn"):
    if new_text.strip() == "":
        st.error("❌ Vraagtekst mag niet leeg zijn.")
        st.stop()

    img_url = ""
    if new_img is not None:
        ext = new_img.name.split(".")[-1].lower()
        if ext not in ("png", "jpg", "jpeg"):
            st.error("❌ Ongeldig afbeeldingsformaat.")
            st.stop()
        safe_vak = vak.replace(" ", "_")
        filename = f"{safe_vak}_new_{int(time.time())}.{ext}"
        url = upload_image_to_github(new_img.read(), filename)
        if url:
            img_url = url

    if new_type == "mc":
        opts = [s.strip() for s in new_opts_str.split(",") if s.strip()]
        choices = opts
    else:
        choices = []

    new_q = {
        "text": new_text,
        "type": new_type,
        "choices": choices,
        "answer": new_answer,
        "image_url": img_url,
    }

    vragen.append(new_q)

    if save_data_to_github(data, f"Nieuwe vraag toegevoegd aan {vak}"):
        st.cache_data.clear()
        st.success("Nieuwe vraag toegevoegd.")
        time.sleep(1)
        st.rerun()
