import tkinter as tk
from models import QuestionBank, HistoryStore
from engine import SpacedRepetitionEngine
from views.start_view import StartView
from views.quiz_view import QuizView
from views.result_view import ResultView
import pandas as pd


class DocQuizApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DocQuiz")
        self.geometry("600x500")

        # Data en engine (nog leeg bij start)
        self.qbank = None
        self.history = HistoryStore()
        self.engine = None

        # Variabelen
        self.questions = []
        self.index = 0
        self.results = {"correct": 0, "wrong": 0}

        # Ophalen van beschikbare vakken (tabbladen uit Excel)
        try:
            xls = pd.ExcelFile("data/quizvragen.xlsx")
            self.available_subjects = xls.sheet_names
        except Exception:
            self.available_subjects = ["DC", "AC", "Vermogen"]

        # Schermen
        self.start_view = StartView(self, self.start_quiz, self.available_subjects)
        self.quiz_view = QuizView(self, self.next_question)
        self.result_view = ResultView(self, self.restart)

        self.show_start()

    # -----------------------
    def show_start(self):
        """Toon startscherm."""
        self.hide_all()
        self.start_view.pack(fill="both", expand=True)

    # -----------------------
    def start_quiz(self, num_questions, sheet_name):
        """Start quiz met x vragen uit gekozen vak (sheet)."""
        excel_path = "data/quizvragen.xlsx"
        QuestionBank.import_from_excel(excel_path, sheet_name)
        self.qbank = QuestionBank("data/questions.json")
        self.engine = SpacedRepetitionEngine(self.qbank, self.history)

        self.questions = self.engine.select_questions(n=num_questions)
        self.index = 0
        self.results = {"correct": 0, "wrong": 0}

        self.show_quiz()

    # -----------------------
    def show_quiz(self):
        """Toon huidige vraag."""
        self.hide_all()
        self.quiz_view.pack(fill="both", expand=True)
        self.quiz_view.show_question(self.questions[self.index])

    # -----------------------
    def next_question(self, question, answer):
        """Verwerk antwoord en ga naar volgende vraag of resultaat."""
        correct = False

        if question.type == "mc":
            correct = (int(answer) == question.answer)
        elif question.type == "tf":
            tf_map = {"Waar": True, "Onwaar": False}
            correct = (tf_map.get(answer) == question.answer)
        elif question.type == "input":
            try:
                val = float(answer.replace(",", "."))
                correct = abs(val - question.answer_numeric) <= question.tolerance
            except ValueError:
                correct = False

        # Geschiedenis bijwerken
        self.history.update_question(question.id, correct)
        self.history.update_tags(question.tags, correct)

        # Score bijwerken
        if correct:
            self.results["correct"] += 1
        else:
            self.results["wrong"] += 1

        # Scorebalk updaten
        self.quiz_view.update_score(self.results["correct"], self.results["wrong"])

        # Volgende vraag of resultaten tonen
        self.index += 1
        if self.index < len(self.questions):
            self.show_quiz()
        else:
            self.show_result()

    # -----------------------
    def show_result(self):
        """Toon resultaten."""
        self.hide_all()
        self.result_view.pack(fill="both", expand=True)
        self.result_view.show_results(self.results, self.history.data["tag_stats"])

    # -----------------------
    def restart(self):
        """Keer terug naar startscherm."""
        self.show_start()

    # -----------------------
    def hide_all(self):
        """Verberg alle schermen."""
        self.start_view.pack_forget()
        self.quiz_view.pack_forget()
        self.result_view.pack_forget()


if __name__ == "__main__":
    app = DocQuizApp()
    app.mainloop()
