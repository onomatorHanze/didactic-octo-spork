import streamlit as st
import json
import requests
import base64
import time
import math
import uuid
from typing import Any, Dict, List, Tuple, Optional

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
def clean(v: Any) -> Any:
    """Zorgt dat None / NaN netjes lege strings worden voor JSON."""
    if v is None:
        return ""
    if isinstance(v, float):
        try:
            if math.isnan(v):
                return ""
        except Exception:
            pass
    return v


def github_get(url: str) -> requests.Response:
    return requests.get(url, headers={"Authorization": f"token {TOKEN}"})


def github_put(url: str, bytes_content: bytes, sha: Optional[str], message: str) -> requests.Response:
    encoded = base64.b64encode(bytes_content).decode("utf-8")
    payload: Dict[str, Any] = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha

    r = requests.put(
        url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )
    return r


def safe_image(url: str) -> None:
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
# JSON laden en opslaan
# -------------------------------------------------------------
def load_data() -> Dict[str, List[Dict[str, Any]]]:
    """Lees altijd vers van GitHub (géén cache)."""
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

    fixed: Dict[str, List[Dict[str, Any]]] = {}
    if not isinstance(data, dict):
        return fixed

    for tab, qs in data.items():
        if isinstance(qs, list):
            # forceer alleen dict-vragen
            fixed[tab] = [q for q in qs if isinstance(q, dict)]
        else:
            fixed[tab] = []
    return fixed


def save_json(data: Dict[str, List[Dict[str, Any]]]) -> bool:
    """Schrijft JSON terug naar GitHub (altijd schoon)."""
    cleaned: Dict[str, List[Dict[str, Any]]] = {}

    for tab, questions in data.items():
        cleaned_list: List[Dict[str, Any]] = []
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
def upload_image(file_bytes: bytes, filename: str) -> Optional[str]:
    path = f"{IMAGE_DIR}/{filename}"
    api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"

    meta = github_get(api_url).json()
    sha = meta.get("sha")

    encoded = base64.b64encode(file_bytes).decode("utf-8")
    payload: Dict[str, Any] = {"message": f"Upload image {filename}", "content": encoded}
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
# Session state initialiseren
# -------------------------------------------------------------
if "edit_ctx" not in st.session_state:
    # None of (vak, index)
    st.session_state["edit_ctx"]: Optional[Tuple[str, int]] = None

if "delete_ctx" not in st.session_state:
    st.session_state["delete_ctx"]: Optional[Tuple[str, int]] = None


# -------------------------------------------------------------
# Data laden & vak kiezen
# -------------------------------------------------------------
data = load_data()

if not data:
    st.warning("Er zijn nog geen vakken in questions.json.")
    st.stop()

st.subheader("📘 Kies een vak")
current_vak = st.selectbox("Vak:", list(data.keys()), key="vak_select")
questions = data.get(current_vak, [])


# -------------------------------------------------------------
# Overzicht vragen
# -------------------------------------------------------------
st.subheader("📄 Overzicht vragen")

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
            st.session_state["edit_ctx"] = (current_vak, i)
            st.session_state["delete_ctx"] = None
            st.experimental_rerun()

    with col4:
        if st.button("❌", key=f"del_btn_{current_vak}_{i}"):
            st.session_state["delete_ctx"] = (current_vak, i)
            st.session_state["edit_ctx"] = None
            st.experimental_rerun()


# -------------------------------------------------------------
# Verwijderen – bevestiging
# -------------------------------------------------------------
if st.session_state["delete_ctx"] is not None:
    dv, di = st.session_state["delete_ctx"]

    if dv in data and 0 <= di < len(data[dv]):
        q = data[dv][di]
        st.markdown("---")
        st.subheader("❓ Deze vraag verwijderen?")
        st.write(f"**[{dv}] {di}: {q.get('text','')}**")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("✔ Ja, verwijderen", key="confirm_delete_yes"):
                data[dv].pop(di)
                if save_json(data):
                    st.success("Vraag verwijderd!")
                    st.session_state["delete_ctx"] = None
                    time.sleep(1)
                    st.experimental_rerun()

        with c2:
            if st.button("✖ Nee, annuleren", key="confirm_delete_no"):
                st.session_state["delete_ctx"] = None
                st.experimental_rerun()


# =============================================================
# Bewerken OF nieuwe vraag – nooit allebei tegelijk
# =============================================================
is_editing = st.session_state["edit_ctx"] is not None

# -------------------------------------------------------------
# BEWERKEN
# -------------------------------------------------------------
if is_editing:
    ev, ei = st.session_state["edit_ctx"]  # type: ignore

    if ev in data and 0 <= ei < len(data[ev]):
        q = data[ev][ei]

        st.markdown("---")
        st.subheader("✏️ Vraag bewerken")

        with st.container(border=True):
            text = st.text_input(
                "Vraagtekst",
                value=clean(q.get("text", "")),
                key=f"edit_text_{ev}_{ei}",
            )

            type_options = ["mc", "tf", "input"]
            current_type = q.get("type", "mc")
            if current_type not in type_options:
                current_type = "mc"
            qtype = st.selectbox(
                "Type",
                type_options,
                index=type_options.index(current_type),
                key=f"edit_type_{ev}_{ei}",
            )

            topic = st.text_input(
                "Topic",
                value=clean(q.get("topic", "")),
                key=f"edit_topic_{ev}_{ei}",
            )

            expl = st.text_area(
                "Uitleg",
                value=clean(q.get("explanation", "")),
                key=f"edit_expl_{ev}_{ei}",
            )

            # type-specifiek
            if qtype == "mc":
                opts = q.get("choices", [])
                if not isinstance(opts, list):
                    opts = []
                opts_str = ", ".join(str(o) for o in opts)
                opts_new_str = st.text_input(
                    "Opties (komma gescheiden)",
                    value=opts_str,
                    key=f"edit_opts_{ev}_{ei}",
                )
                ans_val_raw = q.get("answer", 0)
                try:
                    ans_default = int(ans_val_raw)
                except Exception:
                    ans_default = 0
                ans_new = st.number_input(
                    "Juiste antwoord index",
                    min_value=0,
                    value=ans_default,
                    key=f"edit_ans_mc_{ev}_{ei}",
                )
            elif qtype == "tf":
                opts_new_str = ""
                current_bool = bool(q.get("answer", True))
                ans_new = st.selectbox(
                    "Correct?",
                    [True, False],
                    index=0 if current_bool else 1,
                    key=f"edit_ans_tf_{ev}_{ei}",
                )
            else:
                opts_new_str = ""
                ans_new = st.text_input(
                    "Correct antwoord",
                    value=str(clean(q.get("answer", ""))),
                    key=f"edit_ans_input_{ev}_{ei}",
                )

            st.markdown("### Afbeelding")
            safe_image(q.get("image_url", ""))

            img_file = st.file_uploader(
                "Nieuwe afbeelding (optioneel)",
                type=["png", "jpg", "jpeg"],
                key=f"edit_img_{ev}_{ei}",
            )
            remove_img = st.checkbox(
                "Afbeelding verwijderen",
                key=f"edit_remove_img_{ev}_{ei}",
            )

            c1, c2 = st.columns([2, 1])

            with c1:
                if st.button("💾 Opslaan wijzigingen", key=f"edit_save_btn_{ev}_{ei}"):
                    q["text"] = clean(text)
                    q["type"] = qtype
                    q["topic"] = clean(topic)
                    q["explanation"] = clean(expl)

                    if qtype == "mc":
                        q["choices"] = [
                            s.strip() for s in opts_new_str.split(",") if s.strip()
                        ]
                    else:
                        q["choices"] = []

                    q["answer"] = ans_new

                    if remove_img:
                        q["image_url"] = ""
                    elif img_file is not None:
                        ext = img_file.name.split(".")[-1].lower()
                        fname = f"{ev}_{uuid.uuid4().hex[:6]}.{ext}"
                        url = upload_image(img_file.read(), fname)
                        if url:
                            q["image_url"] = url

                    if save_json(data):
                        st.success("Vraag opgeslagen!")
                        st.session_state["edit_ctx"] = None
                        time.sleep(1)
                        st.experimental_rerun()

            with c2:
                if st.button("Annuleer", key=f"edit_cancel_btn_{ev}_{ei}"):
                    st.session_state["edit_ctx"] = None
                    st.experimental_rerun()

# -------------------------------------------------------------
# NIEUWE VRAAG (alleen als je NIET aan het editen bent)
# -------------------------------------------------------------
if not is_editing:
    st.markdown("---")
    st.subheader("➕ Nieuwe vraag toevoegen")

    text = st.text_input("Vraagtekst", key="new_text")
    qtype = st.selectbox("Type", ["mc", "tf", "input"], key="new_type")
    topic = st.text_input("Topic", key="new_topic")
    expl = st.text_area("Uitleg", key="new_expl")

    if qtype == "mc":
        opts_str = st.text_input("Opties (komma gescheiden)", key="new_opts")
        ans_new = st.number_input("Juiste index", min_value=0, value=0, key="new_ans_mc")
    elif qtype == "tf":
        opts_str = ""
        ans_new = st.selectbox("Correct?", [True, False], key="new_ans_tf")
    else:
        opts_str = ""
        ans_new = st.text_input("Antwoord", key="new_ans_input")

    img_file = st.file_uploader(
        "Afbeelding (optioneel)",
        type=["png", "jpg", "jpeg"],
        key="new_img",
    )

    if st.button("Toevoegen", key="add_new_btn"):
        if text.strip() == "":
            st.error("Vraagtekst mag niet leeg zijn.")
        else:
            img_url = ""
            if img_file is not None:
                ext = img_file.name.split(".")[-1].lower()
                fname = f"{current_vak}_{uuid.uuid4().hex[:6]}.{ext}"
                url = upload_image(img_file.read(), fname)
                if url:
                    img_url = url

            if qtype == "mc":
                opts = [s.strip() for s in opts_str.split(",") if s.strip()]
            else:
                opts = []

            new_question: Dict[str, Any] = {
                "id": f"q{uuid.uuid4().hex[:6]}",
                "text": clean(text),
                "type": qtype,
                "topic": clean(topic),
                "explanation": clean(expl),
                "choices": opts,
                "answer": ans_new,
                "image_url": img_url,
            }

            data[current_vak].append(new_question)

            if save_json(data):
                st.success("Nieuwe vraag toegevoegd!")
                time.sleep(1)
                st.experimental_rerun()
