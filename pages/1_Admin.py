import streamlit as st
import json
import requests
import base64
import uuid
import time
import math

# -------------------------------------------------------------
# SETTINGS & GITHUB CONFIG
# -------------------------------------------------------------
TOKEN = st.secrets["GITHUB_TOKEN"]
OWNER = st.secrets["REPO_OWNER"]
REPO = st.secrets["REPO_NAME"]
JSON_PATH = st.secrets["FILE_PATH"]
IMAGE_DIR = "data/images"

RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{JSON_PATH}"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{JSON_PATH}"

st.set_page_config(page_title="DocQuiz Admin", layout="centered")
st.title("🔧 DocQuiz Admin")


# -------------------------------------------------------------
# HELPER FUNCTIES
# -------------------------------------------------------------
def clean(v):
    """Maak waarden JSON-safe (geen NaN/None)."""
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return v


def github_get(url):
    """GET request met GitHub token."""
    return requests.get(url, headers={"Authorization": f"token {TOKEN}"})


def github_put(url, bytes_data, sha, msg):
    """PUT (create/update) naar GitHub contents API."""
    encoded = base64.b64encode(bytes_data).decode()
    payload = {"message": msg, "content": encoded}
    if sha:
        payload["sha"] = sha
    return requests.put(
        url,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )


def safe_img(url, width=350):
    """Veilig een afbeelding tonen als de URL werkt."""
    if not url:
        return
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            st.image(r.content, width=width)
    except Exception:
        # We negeren errors, geen crash
        pass


# -------------------------------------------------------------
# DATA LOAD & SAVE
# -------------------------------------------------------------
def load_data():
    """
    Laad JSON altijd vers van GitHub.
    Geen caching — wijzigingen zijn direct zichtbaar.
    """
    # Kleine cache-buster op de URL zodat GitHub/proxy niet moeilijk doet
    url = f"{RAW_URL}?ts={int(time.time())}"
    r = github_get(url)

    if r.status_code != 200:
        st.error("❌ Kon JSON niet laden van GitHub.")
        st.code(r.text)
        st.stop()

    try:
        data = r.json()
    except Exception:
        st.error("❌ JSON bestand is corrupt of ongeldig.")
        st.stop()

    # Zorg dat elke tab een lijst is
    fixed = {}
    for tab, qs in data.items():
        fixed[tab] = qs if isinstance(qs, list) else []

    return fixed


def save_json(data):
    """
    Sla de volledige datastructuur op naar GitHub.
    """
    with st.spinner("Bezig met opslaan naar GitHub..."):
        cleaned = {}
        for tab, qs in data.items():
            cl = []
            for q in qs:
                cl.append({k: clean(v) for k, v in q.items()})
            cleaned[tab] = cl

        raw_bytes = json.dumps(cleaned, indent=2, ensure_ascii=False).encode()

        meta_resp = github_get(API_URL)
        sha = None
        if meta_resp.status_code == 200:
            try:
                meta = meta_resp.json()
                sha = meta.get("sha")
            except Exception:
                sha = None

        r = github_put(API_URL, raw_bytes, sha, "Update questions.json")

        if r.status_code not in (200, 201):
            st.error("❌ Opslaan naar GitHub mislukt!")
            st.code(r.text)
            return False

    st.success("✅ Wijzigingen succesvol opgeslagen!")
    return True


def upload_image(bytes_data, filename):
    """
    Upload een afbeelding naar de repo onder IMAGE_DIR
    en retourneer de RAW-URL, of None bij fout.
    """
    path = f"{IMAGE_DIR}/{filename}"
    api = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"

    # Check of bestand al bestaat (voor sha)
    meta_resp = github_get(api)
    sha = None
    if meta_resp.status_code == 200:
        try:
            meta = meta_resp.json()
            sha = meta.get("sha")
        except Exception:
            sha = None

    encoded = base64.b64encode(bytes_data).decode()
    payload = {
        "message": f"Upload {filename}",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(
        api,
        headers={"Authorization": f"token {TOKEN}"},
        data=json.dumps(payload),
    )

    if r.status_code not in (200, 201):
        st.error("❌ Upload van afbeelding mislukt!")
        st.code(r.text)
        return None

    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/{path}"


# -------------------------------------------------------------
# SESSION STATE INITIALISATIE
# -------------------------------------------------------------
def init_session_state():
    if "mode" not in st.session_state:
        st.session_state.mode = "new"  # "new" / "edit"
    if "edit_vak" not in st.session_state:
        st.session_state.edit_vak = None
    if "edit_idx" not in st.session_state:
        st.session_state.edit_idx = None


init_session_state()


# -------------------------------------------------------------
# UI COMPONENTS
# -------------------------------------------------------------
def render_question_row(vak, index, q, data):
    """Render één rij in de vragenlijst."""
    c1, c2, c3 = st.columns([7, 1, 1])

    title = q.get("text", "")
    short = (title[:70] + "…") if len(title) > 70 else title

    with c1:
        st.write(f"**{index} — {short}**")

    with c2:
        if st.button("✏️", key=f"edit_btn_{vak}_{index}"):
            st.session_state.mode = "edit"
            st.session_state.edit_vak = vak
            st.session_state.edit_idx = index
            st.rerun()

    with c3:
        if st.button("❌", key=f"del_btn_{vak}_{index}"):
            if "confirm_delete" not in st.session_state:
                st.session_state.confirm_delete = None

            st.session_state.confirm_delete = (vak, index)


def handle_delete_if_confirmed(data):
    """Toon confirm dialoog bij delete en voer eventueel uit."""
    if "confirm_delete" not in st.session_state or st.session_state.confirm_delete is None:
        return

    vak, idx = st.session_state.confirm_delete

    st.warning(f"⚠️ Weet je zeker dat je vraag #{idx} uit vak '{vak}' wilt verwijderen?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Ja, verwijderen", key="confirm_delete_yes"):
            try:
                data[vak].pop(idx)
            except IndexError:
                st.error("Kon de vraag niet vinden om te verwijderen.")
                st.session_state.confirm_delete = None
                st.rerun()

            if save_json(data):
                st.session_state.confirm_delete = None
                st.rerun()
    with c2:
        if st.button("Annuleren", key="confirm_delete_no"):
            st.session_state.confirm_delete = None
            st.rerun()


def parse_mc_choices(raw: str):
    """Maak lijst van opties uit een tekstveld (komma-gescheiden)."""
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


# -------------------------------------------------------------
# EDIT FORM
# -------------------------------------------------------------
def render_edit_form(vak, idx, data):
    """Formulier om een bestaande vraag te bewerken."""
    try:
        q = data[vak][idx]
    except (KeyError, IndexError):
        st.error("Kon de te bewerken vraag niet vinden.")
        st.session_state.mode = "new"
        return

    st.markdown("---")
    st.subheader(f"✏️ Vraag bewerken — [{vak}] #{idx}")

    # Basisvelden
    text = st.text_input("Vraagtekst", value=q.get("text", ""), key="e_text")

    type_options = ["mc", "tf", "input"]
    qtype = q.get("type", "mc")
    if qtype not in type_options:
        qtype = "mc"

    qtype = st.selectbox(
        "Type",
        type_options,
        index=type_options.index(qtype),
        key="e_type",
    )

    topic = st.text_input("Topic", value=q.get("topic", ""), key="e_topic")
    expl = st.text_area("Uitleg", value=q.get("explanation", ""), key="e_expl")

    # Antwoordvelden per type
    ans = q.get("answer", "")
    choices = q.get("choices", []) or []

    if qtype == "mc":
        opts_str = ", ".join(choices)
        opts = st.text_input("Opties (komma-gescheiden)", value=opts_str, key="e_opts_mc")
        try:
            default_idx = int(ans)
        except Exception:
            default_idx = 0
        ans_mc = st.number_input(
            "Correcte index (0-based)",
            value=default_idx,
            min_value=0,
            step=1,
            key="e_ans_mc",
        )
        new_answer = ans_mc
        new_choices = parse_mc_choices(opts)

    elif qtype == "tf":
        # True / False
        bool_answer = bool(ans)
        ans_tf = st.selectbox(
            "Correct?",
            [True, False],
            index=0 if bool_answer else 1,
            key="e_ans_tf",
        )
        new_answer = ans_tf
        new_choices = []

    else:  # "input"
        ans_inp = st.text_input("Antwoord (vrije tekst)", value=str(ans), key="e_ans_input")
        new_answer = ans_inp
        new_choices = []

    # Afbeelding
    st.markdown("### Afbeelding")
    safe_img(q.get("image_url"))
    new_img = st.file_uploader("Nieuwe afbeelding (optioneel)", type=["png", "jpg", "jpeg"], key="e_img")
    rem_img = st.checkbox("Verwijder huidige afbeelding", key="e_rem")

    # Actieknoppen
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Opslaan", key="save_edit"):
            # Updaten in geheugen
            q["text"] = text
            q["type"] = qtype
            q["topic"] = topic
            q["explanation"] = expl
            q["choices"] = new_choices
            q["answer"] = new_answer

            # Afbeelding verwerken
            if rem_img:
                q["image_url"] = ""
            elif new_img is not None:
                ext = new_img.name.split(".")[-1]
                fname = f"{vak}_{uuid.uuid4().hex[:6]}.{ext}"
                url = upload_image(new_img.read(), fname)
                if url:
                    q["image_url"] = url

            # Opslaan naar GitHub
            if save_json(data):
                st.session_state.mode = "new"
                st.rerun()

    with c2:
        if st.button("Annuleren", key="cancel_edit"):
            st.session_state.mode = "new"
            st.rerun()


# -------------------------------------------------------------
# NEW QUESTION FORM
# -------------------------------------------------------------
def render_new_question_form(vak, data):
    """Formulier voor nieuwe vraag."""
    st.markdown("---")
    st.subheader("➕ Nieuwe vraag toevoegen")

    nt = st.text_input("Vraagtekst", key="n_text")
    ntp = st.selectbox("Type", ["mc", "tf", "input"], key="n_type")
    ntopic = st.text_input("Topic", key="n_topic")
    nexp = st.text_area("Uitleg", key="n_expl")

    if ntp == "mc":
        nop = st.text_input("Opties (komma-gescheiden)", key="n_opts")
        nans_mc = st.number_input(
            "Correcte index (0-based)",
            min_value=0,
            value=0,
            step=1,
            key="n_ans_mc",
        )
        answer = nans_mc
        choices = parse_mc_choices(nop)

    elif ntp == "tf":
        choices = []
        answer = st.selectbox("Correct?", [True, False], key="n_ans_tf")

    else:  # "input"
        choices = []
        answer = st.text_input("Antwoord (vrije tekst)", key="n_ans_input")

    nimg = st.file_uploader("Afbeelding (optioneel)", type=["png", "jpg", "jpeg"], key="n_img")

    if st.button("Toevoegen", key="btn_add"):
        if nt.strip() == "":
            st.error("❌ Vraagtekst mag niet leeg zijn.")
            return

        img_url = ""
        if nimg is not None:
            ext = nimg.name.split(".")[-1]
            fname = f"{vak}_{uuid.uuid4().hex[:6]}.{ext}"
            url = upload_image(nimg.read(), fname)
            if url:
                img_url = url

        newq = {
            "id": f"q{uuid.uuid4().hex[:6]}",
            "text": nt,
            "type": ntp,
            "topic": ntopic,
            "explanation": nexp,
            "choices": choices,
            "answer": answer,
            "image_url": img_url,
        }

        data[vak].append(newq)

        if save_json(data):
            st.rerun()


# -------------------------------------------------------------
# MAIN APP FLOW
# -------------------------------------------------------------
def main():
    # Data laden
    data = load_data()

    # Vakken selecteren
    st.subheader("📘 Kies een vak")
    vakken = list(data.keys())
    if not vakken:
        st.error("Er zijn nog geen vakken gedefinieerd in het JSON bestand.")
        st.stop()

    vak = st.selectbox("Vak:", vakken, key="vak_select")
    vragen = data.get(vak, [])

    # Overzicht vragen
    st.subheader("📄 Overzicht vragen")
    if not vragen:
        st.info("Nog geen vragen in dit vak. Voeg de eerste vraag toe hieronder 👇")
    else:
        for i, q in enumerate(vragen):
            render_question_row(vak, i, q, data)

    # Delete confirm dialoog (als nodig)
    handle_delete_if_confirmed(data)

    # Edit / New formulier
    if st.session_state.mode == "edit":
        render_edit_form(st.session_state.edit_vak, st.session_state.edit_idx, data)
    else:
        render_new_question_form(vak, data)


if __name__ == "__main__":
    main()
