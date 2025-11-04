import random
import time
from datetime import datetime, timedelta
from models import QuestionBank, HistoryStore

class SpacedRepetitionEngine:
    """
    Deze klasse kiest vragen op basis van voortgang (Leitner-principe).
    """
    # Wachttijd per box (in minuten of dagen)
    BOX_WAIT = [
        timedelta(minutes=0),      # 0 = altijd weer tonen
        timedelta(minutes=10),
        timedelta(days=1),
        timedelta(days=3),
        timedelta(days=7),
        timedelta(days=21)
    ]

    def __init__(self, qbank: QuestionBank, history: HistoryStore):
        self.qbank = qbank
        self.history = history

    def _calc_weight(self, q):
        """
        Bereken een gewicht per vraag: hoe hoger, hoe groter kans dat deze gekozen wordt.
        """
        h = self.history.data["history"].get(q.id)
        base = 1 + 0.2 * q.difficulty   # moeilijkere vragen iets zwaarder

        if not h:   # nog nooit beantwoord
            return base * 3

        # bereken tijd sinds laatste poging
        last_time = datetime.fromisoformat(h["last"])
        box = h["box"]
        correct = h["correct"]
        wrong = h["wrong"]

        # Is vraag 'overdue'? (tijd sinds laatste > wachttijd voor die box)
        overdue = (datetime.now() - last_time) > self.BOX_WAIT[box]
        if overdue:
            base *= 2

        # Extra gewicht voor zwakke prestaties
        if wrong > correct:
            base *= 1.5

        return base
    
    
    
    def select_questions(self, n=5, tags=None):
        """
        Selecteer n vragen met weging.
        """
        candidates = self.qbank.filter(tags=tags)
        weights = [self._calc_weight(q) for q in candidates]
        print("DEBUG candidates type:", type(candidates), "len attr:", getattr(candidates, "len", None))
        print("DEBUG min is:", min, "type:", type(min))
        return random.choices(candidates, weights=weights, k=min(n, len(candidates)))
