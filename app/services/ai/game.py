"""Сервис игрового симулятора продаж («🎮 Симулятор продаж»).

Игровой тренажёр квалификации лидов:
- Симулирует диалог с потенциальным клиентом бизнеса.
- Вычисляет оценку квалификации (0-100 баллов) по правилам общения,
  обработке возражений, выявлению потребностей и закрытию на целевое действие.
- Выдаёт итоговую карточку результатов с рекомендациями.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GameScenario:
    id: str
    title: str
    client_persona: str
    initial_message: str
    objections: list[str]


SCENARIOS: dict[str, GameScenario] = {
    "b2b": GameScenario(
        id="b2b",
        title="B2B-клиент (Владелец агентства)",
        client_persona="Алексей, владелец маркетингового агентства. Ищет решение для обработки заявок 24/7.",
        initial_message="Добрый день! Увидел вашего AI-Сотрудника. Подскажите, как он работает и сколько стоит подключение?",
        objections=[
            "А если бот наговорит лишнего клиенту или ошибётся в цене?",
            "У нас специфическая ниша, не уверен, что ИИ справится без нашего менеджера.",
            "Звучит интересно. Что нужно, чтобы протестировать на наших данных?",
        ],
    ),
    "services": GameScenario(
        id="services",
        title="Сфера услуг (Сеть салонов / Клиника)",
        client_persona="Елена, управляющая сетью клиник. Много ночных пропущенных звонков и заявок.",
        initial_message="Здравствуйте! Мы теряем клиентов из-за того, что администраторы не успевают отвечать вечером. Что вы предлагаете?",
        objections=[
            "Наши клиенты привыкли к живому общению, не отпугнёт ли их робот?",
            "Какая гарантия, что заявка не потеряется ночью?",
            "Хорошо, а можно ли записаться на демонстрацию?",
        ],
    ),
}


@dataclass
class GameSessionState:
    scenario_id: str = "b2b"
    turn: int = 1
    max_turns: int = 4
    score: int = 0
    history: list[dict[str, str]] = field(default_factory=list)
    lead_status: str = "Холодный лид ❄️"

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "turn": self.turn,
            "max_turns": self.max_turns,
            "score": self.score,
            "history": self.history,
            "lead_status": self.lead_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameSessionState:
        return cls(
            scenario_id=data.get("scenario_id", "b2b"),
            turn=data.get("turn", 1),
            max_turns=data.get("max_turns", 4),
            score=data.get("score", 0),
            history=data.get("history", []),
            lead_status=data.get("lead_status", "Холодный лид ❄️"),
        )


class SalesGameService:
    """Сервис управления сессиями симулятора и оценки ходов."""

    def start_game(self, scenario_id: str = "b2b") -> tuple[GameSessionState, str]:
        scenario = SCENARIOS.get(scenario_id, SCENARIOS["b2b"])
        state = GameSessionState(
            scenario_id=scenario.id,
            turn=1,
            max_turns=4,
            score=0,
            history=[{"role": "client", "text": scenario.initial_message}],
            lead_status="Холодный лид ❄️",
        )
        intro = (
            f"🎮 <b>Игровой тренажёр: {scenario.title}</b>\n\n"
            f"👤 <b>Клиент:</b> {scenario.client_persona}\n\n"
            f"💬 <b>Сообщение клиента:</b>\n«{scenario.initial_message}»\n\n"
            f"🎯 <b>Ваша задача:</b> Ответить клиенту, выявить потребность, обработать возражения и закрыть на запись/демо.\n"
            f"<i>Раунд 1 из {state.max_turns}. Напишите ваш ответ следующим сообщением!</i>"
        )
        return state, intro

    def process_turn(
        self, state: GameSessionState, user_text: str
    ) -> tuple[GameSessionState, str, bool]:
        scenario = SCENARIOS.get(state.scenario_id, SCENARIOS["b2b"])
        text = user_text.strip()

        # Оценка качества хода
        turn_score = 15  # Базовый балл за ответ
        feedback_points = []

        if len(text) > 20:
            turn_score += 5
        if "?" in text:
            turn_score += 5  # Задавание встречного квалифицирующего вопроса
            feedback_points.append("задан квалифицирующий вопрос")
        if any(w in text.lower() for w in ["демо", "тест", "попробу", "запис", "созвон", "тариф", "бесплатн"]):
            turn_score += 5  # Призыв к действию / оффер
            feedback_points.append("есть призыв к действию / оффер")

        turn_score = min(25, turn_score)
        state.score += turn_score
        state.history.append({"role": "user", "text": text})

        # Обновление статуса лида
        if state.score >= 80:
            state.lead_status = "Горячий лид 🔥 (Готов к сделке)"
        elif state.score >= 50:
            state.lead_status = "Тёплый лид 🟡 (Проявил интерес)"
        else:
            state.lead_status = "Холодный лид ❄️"

        # Проверка завершения игры
        if state.turn >= state.max_turns:
            summary = self._generate_final_summary(state, scenario)
            return state, summary, True  # True = game finished

        # Следующий ход клиента
        objection_idx = min(state.turn - 1, len(scenario.objections) - 1)
        next_client_msg = scenario.objections[objection_idx]

        state.turn += 1
        state.history.append({"role": "client", "text": next_client_msg})

        reply = (
            f"💬 <b>Ответ клиента (Раунд {state.turn}/{state.max_turns}):</b>\n«{next_client_msg}»\n\n"
            f"📊 <i>Текущий счет: {state.score}/100 | Статус: {state.lead_status}</i>\n\n"
            f"Напишите ваш ответ клиенту:"
        )
        return state, reply, False

    def _generate_final_summary(self, state: GameSessionState, scenario: GameScenario) -> str:
        score = min(100, state.score)
        if score >= 85:
            rank = "🏆 Мастер квалификации"
            advice = "Отличная работа! Вы провели лида по всей воронке и закрыли сделку."
        elif score >= 60:
            rank = "👍 Хороший продавец"
            advice = "Хороший результат. Старайтесь чаще задавать квалифицирующие вопросы и делать чёткий призыв к действию."
        else:
            rank = "🌱 Начинающий"
            advice = "Клиент остался в сомнениях. Используйте открытые вопросы и предлагайте конкретный следующий шаг (демо/тест)."

        return (
            f"🏁 <b>Игра завершена! Итоги тренажёра</b>\n\n"
            f"📊 <b>Ваш результат:</b> {score}/100 баллов\n"
            f"🎖 <b>Звание:</b> {rank}\n"
            f"🎯 <b>Итоговый статус лида:</b> {state.lead_status}\n\n"
            f"💡 <b>Анализ:</b> {advice}\n\n"
            f"🚀 <i>Подключите базу знаний в /knowledge, чтобы AI-Сотрудник автоматически отвечал клиентам 24/7 с максимальной конверсией!</i>"
        )
