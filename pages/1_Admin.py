import streamlit as st
import json
import requests
import base64
import time
import math
import uuid

# -------------------------------------------------------------
# CONFIG – via Streamlit Secrets
# -------------------------------------------------------------
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
JSON_PATH = st.secrets["FILE_PATH"]           # bijv. "data/questions.json"
IMAGE_DIR = "data/images"

JSON_RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{JSON_PATH}"
JSON_API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{JSON_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin – Beheer quizvragen")


# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------
def clean(v):
    """Zorgt dat None / NaN netjes lege strings worden voor JSON."""
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return v


def github_get(url: str):
    return requests.get(url, headers={"Authorization": f"token {TOKEN}"})


def github_put(url: str, bytes_content: bytes, sha: str | None, message: str):
    encoded = base64.b64encode(bytes_content).decode()
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(
        url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )
    return r


def safe_image(url: str):
    """Afbeelding tonen zonder Streamlit te laten crashen."""
    if not isinstance(url, str) or not url.strip():
        st.caption("Geen afbeelding.")
        return

    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            st.image(r.content, width=350)
        else:
            st.caption("⚠️ Afbeelding kon niet geladen worden.")
    except Exception:
        st.caption("⚠️ Fout bij laden van afbeelding.")


# -------------------------------------------------------------
# JSON laden & opslaan
# -------------------------------------------------------------
def load_data() -> dict:
    """Lees questions.json direct van GitHub."""
    r = github_get(JSON_RAW_URL)
    if r.status_code != 200:
        st.error(f"Kon JSON niet laden ({r.status_code}).")
        try:
            st.code(r.text, language="json")
        except Exception:
            pass
        st.stop()

    try:
        data = r.json()
    except Exception:
        st.error("JSON kon niet worden geparsed. Controleer vragenbestand op GitHub.")
        st.stop()

    # Extra defensief: zorg dat iedere tab een lijst is
    fixed: dict[str, list[dict]] = {}
    if isinstance(data, dict):
        for tab, qs in data.items():
            if isinstance(tab, str) and isinstance(qs, list):
                fixed[tab] = qs
    return fixed


def save_json(data: dict) -> bool:
    """Schrijf JSON terug naar GitHub (altijd schoon)."""
    cleaned: dict[str, list[dict]] = {}

    for tab, questions in data.items():
        cleaned_list = []
        if not isinstance(questions, list):
            continue
        for q in questions:
            if not isinstance(q, dict):
                continue
            q2 = {k: clean(v) for k, v in q.items()}
            cleaned_list.append(q2)
        cleaned[tab] = cleaned_list

    raw_bytes = json.dumps(cleaned, indent=2, ensure_ascii=False).encode("utf-8")

    meta = github_get(JSON_API_URL).json()
    sha = meta.get("sha")

    r = github_put(JSON_API_URL, raw_bytes, sha, "Update questions.json via Admin")

    if r.status_code not in (200, 201):
        st.error(f"❌ Opslaan van JSON mislukt (status {r.status_code}).")
        try:
            st.code(r.text, language="json")
        except Exception:
            pass
        return False

    return True


# -------------------------------------------------------------
# Afbeelding uploaden
# -------------------------------------------------------------
def upload_image(file_bytes: bytes, filename: str) -> str | None:
    path = f"{IMAGE_DIR}/{filename}"
    api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"

    meta = github_get(api_url).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode()
    payload = {"message": f"Upload image {filename}", "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(
        api_url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )

    if r.status_code not in (200, 201):
        st.error(f"❌ Upload van afbeelding mislukt (status {r.status_code}).")
        try:
            st.code(r.text, language="json")
        except Exception:
            pass
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{path}"


# -------------------------------------------------------------
# Session state initialisatie
# -------------------------------------------------------------
for key, default in [
    ("edit_vak", None),
    ("edit_index", None),
    ("del_vak", None),
    ("del_index", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# -------------------------------------------------------------
# Data laden & vak kiezen
# -------------------------------------------------------------
data = load_data()

if not data:
    st.warning("Er zijn nog geen vragen in questions.json.")
    st.stop()

st.subheader("📘 Kies een vak")
current_vak = st.selectbox("Vak:", list(data.keys()), key="vak_select")
questions = data[current_vak]

# Bepaal of we nu in 'edit mode' zitten
is_editing = st.session_state["edit_vak"] is not None


# -------------------------------------------------------------
# Overzicht vragen
# -------------------------------------------------------------
st.subheader("📄 Overzicht vragen")

if not questions:
    st.info("Er zijn nog geen vragen voor dit vak.")
else:
    for i, q in enumerate(questions):
        col1, col2, col3, col4 = st.columns([6, 1, 1, 1])

        with col1:
            txt = str(q.get("text", ""))
            short = txt[:80] + ("…" if len(txt) > 80 else "")
            st.write(f"**{i}: {short}**")

        with col2:
            if q.get("image_url"):
                st.caption("🖼")

        with col3:
            if st.button("✏️", key=f"edit_btn_{current_vak}_{i}"):
                st.session_state["edit_vak"] = current_vak
                st.session_state["edit_index"] = i
                st.session_state["del_vak"] = None
                st.session_state["del_index"] = None
                st.rerun()

        with col4:
            if st.button("❌", key=f"del_btn_{current_vak}_{i}"):
                st.session_state["del_vak"] = current_vak
                st.session_state["del_index"] = i
                st.session_state["edit_vak"] = None
                st.session_state["edit_index"] = None
                st.rerun()


# -------------------------------------------------------------
# Verwijderen – bevestiging
# -------------------------------------------------------------
if (
    st.session_state["del_vak"] is not None
    and st.session_state["del_index"] is not None
):
    dv = st.session_state["del_vak"]
    di = st.session_state["del_index"]

    if dv in data and 0 <= di < len(data[dv]):
        q = data[dv][di]
        st.markdown("---")
        st.subheader("❓ Deze vraag verwijderen?")
        st.write(f"**[{dv}] {di}: {q.get('text', '')}**")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("✔ Ja, verwijderen", key="del_confirm_yes"):
                data[dv].pop(di)
                if save_json(data):
                    st.success("Vraag verwijderd!")
                    st.session_state["del_vak"] = None
                    st.session_state["del_index"] = None
                    time.sleep(1)
                    st.rerun()

        with c2:
            if st.button("✖ Nee, annuleren", key="del_confirm_no"):
                st.session_state["del_vak"] = None
                st.session_state["del_index"] = None
                st.rerun()


# -------------------------------------------------------------
# Bewerken – alleen als we in edit mode zijn
# -------------------------------------------------------------
if (
    st.session_state["edit_vak"] is not None
    and st.session_state["edit_index"] is not None
):
    ev = st.session_state["edit_vak"]
    ei = st.session_state["edit_index"]

    if ev in data and 0 <= ei < len(data[ev]):
        q = data[ev][ei]

        st.markdown("---")
        st.subheader(f"✏️ Vraag bewerken – [{ev}] index {ei}")

        with st.container(border=True):
            text = st.text_input(
                "Vraagtekst",
                value=clean(q.get("text", "")),
                key="edit_text",
            )

            type_options = ["mc", "tf", "input"]
            current_type = q.get("type", "mc")
            if current_type not in type_options:
                current_type = "mc"
            qtype = st.selectbox(
                "Type",
                type_options,
                index=type_options.index(current_type),
                key="edit_type",
            )

            topic = st.text_input(
                "Topic",
                value=clean(q.get("topic", "")),
                key="edit_topic",
            )
            expl = st.text_area(
                "Uitleg",
                value=clean(q.get("explanation", "")),
                key="edit_expl",
            )

            # type-specifiek
            if qtype == "mc":
                opts = q.get("choices", [])
                if not isinstance(opts, list):
                    opts = []
                opts_str = ", ".join(str(o) for o in opts)
                new_opts_str = st.text_input(
                    "Opties (komma gescheiden)",
                    value=opts_str,
                    key="edit_opts",
                )
                ans_val = q.get("answer", 0)
                try:
                    ans_default = int(ans_val)
                except Exception:
                    ans_default = 0
                ans = st.number_input(
                    "Juiste antwoord index",
                    min_value=0,
                    value=ans_default,
                    key="edit_ans_mc",
                )
            elif qtype == "tf":
                new_opts_str = ""
                current_bool = bool(q.get("answer", True))
                ans = st.selectbox(
                    "Correct?",
                    [True, False],
                    index=0 if current_bool else 1,
                    key="edit_ans_tf",
                )
            else:  # input
                new_opts_str = ""
                ans = st.text_input(
                    "Correct antwoord",
                    value=str(clean(q.get("answer", ""))),
                    key="edit_ans_input",
                )

            # Afbeelding
            st.markdown("### Afbeelding")
            safe_image(q.get("image_url", ""))

            img_file = st.file_uploader(
                "Nieuwe afbeelding (optioneel)",
                type=["png", "jpg", "jpeg"],
                key="edit_img",
            )
            remove_img = st.checkbox(
                "Afbeelding verwijderen",
                key="edit_remove_img",
            )

            col_save, col_cancel = st.columns([2, 1])

            with col_save:
                if st.button("💾 Opslaan wijzigingen", key="edit_save_btn"):
                    q["text"] = clean(text)
                    q["type"] = qtype
                    q["topic"] = clean(topic)
                    q["explanation"] = clean(expl)

                    if qtype == "mc":
                        q["choices"] = [
                            s.strip() for s in new_opts_str.split(",") if s.strip()
                        ]
                    else:
                        q["choices"] = []

                    q["answer"] = ans

                    if remove_img:
                        q["image_url"] = ""
                    elif img_file:
                        ext = img_file.name.split(".")[-1].lower()
                        fname = f"{ev}_{uuid.uuid4().hex[:6]}.{ext}"
                        url = upload_image(img_file.read(), fname)
                        if url:
                            q["image_url"] = url

                    if save_json(data):
                        st.success("Vraag opgeslagen!")
                        st.session_state["edit_vak"] = None
                        st.session_state["edit_index"] = None
                        time.sleep(1)
                        st.rerun()

            with col_cancel:
                if st.button("Annuleer", key="edit_cancel_btn"):
                    st.session_state["edit_vak"] = None
                    st.session_state["edit_index"] = None
                    st.rerun()


# -------------------------------------------------------------
# Nieuwe vraag toevoegen – alleen als we NIET aan het editen zijn
# -------------------------------------------------------------
if st.session_state["edit_vak"] is None:
    st.markdown("---")
    st.subheader("➕ Nieuwe vraag toevoegen")

    new_text = st.text_input("Vraagtekst", key="new_text")
    new_type = st.selectbox("Type", ["mc", "tf", "input"], key="new_type")
    new_topic = st.text_input("Topic", key="new_topic")
    new_expl = st.text_area("Uitleg", key="new_expl")

    if new_type == "mc":
        new_opts_str = st.text_input("Opties (komma gescheiden)", key="new_opts")
        new_ans = st.number_input(
            "Juiste index",
            min_value=0,
            value=0,
            key="new_ans_mc",
        )
    elif new_type == "tf":
        new_opts_str = ""
        new_ans = st.selectbox("Correct?", [True, False], key="new_ans_tf")
    else:
        new_opts_str = ""
        new_ans = st.text_input("Antwoord", key="new_ans_input")

    new_img = st.file_uploader(
        "Afbeelding (optioneel)",
        type=["png", "jpg", "jpeg"],
        key="new_img",
    )

    if st.button("Toevoegen", key="add_new_btn"):
        if new_text.strip() == "":
            st.error("Vraagtekst mag niet leeg zijn.")
        else:
            img_url = ""
            if new_img:
                ext = new_img.name.split(".")[-1].lower()
                fname = f"{current_vak}_{uuid.uuid4().hex[:6]}.{ext}"
                url = upload_image(new_img.read(), fname)
                if url:
                    img_url = url

            if new_type == "mc":
                opts = [s.strip() for s in new_opts_str.split(",") if s.strip()]
            else:
                opts = []

            new_question = {
                "id": f"q{uuid.uuid4().hex[:6]}",
                "text": clean(new_text),
                "type": new_type,
                "topic": clean(new_topic),
                "explanation": clean(new_expl),
                "choices": opts,
                "answer": new_ans,
                "image_url": img_url,
            }

            data[current_vak].append(new_question)

            if save_json(data):
                st.success("Nieuwe vraag toegevoegd!")
                time.sleep(1)
                st.rerun()
