import json
import os
import csv
import ast
from datetime import datetime
from builtins import min
import pandas as pd


# ------------------------------------------------------------
# 1️⃣ Klasse voor één quizvraag
# ------------------------------------------------------------
class Question:
    def __init__(self, id, type, topic, text, tags=None,
                 choices=None, answer=None, answer_numeric=None,
                 tolerance=0.0, explanation=None, image_path=None,
                 formula_latex=None, difficulty=2):
        self.id = id
        self.type = type
        self.topic = topic
        self.text = text
        self.tags = tags or []
        self.choices = choices or []
        self.answer = answer
        self.answer_numeric = answer_numeric
        self.tolerance = tolerance
        self.explanation = explanation
        self.image_path = image_path
        self.formula_latex = formula_latex
        self.difficulty = difficulty


# ------------------------------------------------------------
# 2️⃣ Verzameling van vragen + CSV/Excel import
# ------------------------------------------------------------
class QuestionBank:
    def __init__(self, path="data/questions.json"):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Bestand niet gevonden: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.questions = [Question(**q) for q in data.get("questions", [])]

    def filter(self, topics=None, tags=None):
        """Filter vragen op onderwerp of tag."""
        result = self.questions
        if topics:
            result = [q for q in result if q.topic in topics]
        if tags:
            result = [q for q in result if any(t in q.tags for t in tags)]
        return result

    # ---- CSV import ----
    @staticmethod
    def import_from_csv(csv_path: str, json_path: str = "data/questions.json"):
        """Importeer vragen uit CSV en sla op in JSON."""
        questions = []
        try:
            with open(csv_path, newline='', encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    q = {
                        "id": row["id"],
                        "type": row["type"],
                        "topic": row["topic"],
                        "text": row["text"],
                        "difficulty": int(row.get("difficulty", 1)),
                        "choices": ast.literal_eval(row["choices"]) if row["choices"] else [],
                        "answer": ast.literal_eval(row["answer"]) if row["answer"] else None,
                        "explanation": row.get("explanation", ""),
                        "image_path": row.get("image_path", ""),
                        "formula_latex": row.get("formula_latex", ""),
                        "tags": ast.literal_eval(row["tags"]) if row["tags"] else [],
                    }
                    questions.append(q)

            data = {"meta": {"title": "Imported from CSV", "version": 1}, "questions": questions}

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            print(f"✅ CSV succesvol geïmporteerd ({len(questions)} vragen). Opgeslagen in {json_path}")

        except Exception as e:
            print(f"❌ Fout bij importeren CSV: {e}")

    # ---- Excel import ----
    @staticmethod
    def import_from_excel(excel_path: str, sheet_name: str = "DC", json_path: str = "data/questions.json"):
        """Importeer vragen uit een Excel-tabblad en sla op als JSON."""
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            questions = []

            for _, row in df.iterrows():
                q = {
                    "id": str(row["id"]),
                    "type": row["type"],
                    "topic": row["topic"],
                    "text": row["text"],
                    "choices": ast.literal_eval(str(row["choices"])) if pd.notna(row["choices"]) else [],
                    "answer": ast.literal_eval(str(row["answer"])) if pd.notna(row["answer"]) else None,
                    "explanation": row.get("explanation", ""),
                    "image_path": row.get("image_path", ""),
                    "formula_latex": row.get("formula_latex", ""),
                    "tags": ast.literal_eval(str(row["tags"])) if pd.notna(row["tags"]) else [],
                    "difficulty": int(row.get("difficulty", 1)),
                }
                if q["type"] == "input":
                    # Als answer_numeric niet is ingevuld, neem de numerieke waarde van 'answer'
                    try:
                        q["answer_numeric"] = float(q["answer"])
                    except (TypeError, ValueError):
                        q["answer_numeric"] = None
                else:
                    q["answer_numeric"] = None

                
                questions.append(q)

            data = {"meta": {"source": excel_path, "sheet": sheet_name}, "questions": questions}

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            print(f"✅ {len(questions)} vragen uit tabblad '{sheet_name}' geïmporteerd en opgeslagen in {json_path}")
        except Exception as e:
            print(f"❌ Fout bij importeren Excel: {e}")


# ------------------------------------------------------------
# 3️⃣ Voortgang en resultaten
# ------------------------------------------------------------import json
import requests
from datetime import datetime
import base64
import os


class HistoryStore:
    """
    History wordt opgeslagen op GitHub via dezelfde methode als questions.json.
    """

    def __init__(self, user="default",
                 token=None,
                 repo_owner=None,
                 repo_name=None):

        self.user = user
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.repo_owner = repo_owner or os.environ.get("REPO_OWNER")
        self.repo_name = repo_name or os.environ.get("REPO_NAME")

        self.path = f"data/history/{self.user}.json"

        self.api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/{self.path}"
        self.headers = {"Authorization": f"token {self.token}"}

        self.data = self._load()

    # ---------------------------------------------------------
    # Laden
    # ---------------------------------------------------------
    def _load(self):
        r = requests.get(self.api_url, headers=self.headers)

        if r.status_code == 200:
            content = r.json().get("content", "")
            decoded = base64.b64decode(content).decode("utf-8")
            return json.loads(decoded)
        else:
            # Nieuw bestand aanmaken
            data = {"user": self.user, "history": {}, "tag_stats": {}}
            self._save(data)
            return data

    # ---------------------------------------------------------
    # Opslaan
    # ---------------------------------------------------------
    def _save(self, content):
        encoded = base64.b64encode(json.dumps(content, indent=2).encode()).decode()

        # probeer sha te lezen
        meta = requests.get(self.api_url, headers=self.headers).json()
        sha = meta.get("sha", None)

        payload = {
            "message": f"Update history {self.user}",
            "content": encoded,
        }
        if sha:
            payload["sha"] = sha

        requests.put(self.api_url, headers=self.headers, json=payload)

    # ---------------------------------------------------------
    # Update vraagresultaat
    # ---------------------------------------------------------
    def update_question(self, qid, is_correct):
        hist = self.data["history"].get(qid, {"last": None, "box": 0, "correct": 0, "wrong": 0})

        hist["last"] = datetime.now().isoformat()

        if is_correct:
            hist["box"] = min(hist["box"] + 1, 5)
            hist["correct"] += 1
        else:
            hist["box"] = 0
            hist["wrong"] += 1

        self.data["history"][qid] = hist
        self._save(self.data)


