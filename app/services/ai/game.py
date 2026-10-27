"""VIP Симулятор продаж и квалификации лидов на базе AI («/game»)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameScenario:
    id: str
    title: str
    icon: str
    client_persona: str
    deal_value: str
    initial_message: str
    objections: list[str]
    hints: list[str]


SCENARIOS: dict[str, GameScenario] = {
    "b2b": GameScenario(
        id="b2b",
        title="B2B Enterprise SaaS",
        icon="🏢",
        client_persona="Алексей, ИТ-директор ритейл-сети. Опасается утечек данных и сложной интеграции.",
        deal_value="1 200 000 ₽ / год",
        initial_message="Добрый день. Мы ищем AI-платформу для автоматизации поддержки, но критична безопасность данных.",
        objections=[
            "У нас строго не разрешено выгружать данные клиентов в публичные облака. Как гарантируется безопасность?",
            "Интеграция с нашей CRM (1С/Bitrix24) займет полгода и будет стоить миллионы?",
            "Звучит заманчиво, но топ-менеджмент сомневается в ROI. Нам нужны гарантии.",
        ],
        hints=[
            "💡 <b>Совет наставника:</b> Подчеркните локальное хранение данных, шифрование и возможность On-Premise / приватного контура.",
            "💡 <b>Совет наставника:</b> Расскажите про готовые Webhook API и развертывание базовой базы знаний за 1 день.",
            "💡 <b>Совет наставника:</b> Предложите бесплатный пилотный проект на 14 дней с оцифровкой конверсий.",
        ],
    ),
    "services": GameScenario(
        id="services",
        title="Сфера услуг (Агентство недвижимости)",
        icon="🏠",
        client_persona="Елена, руководитель отдела продаж. Клиенты уходят из-за долгих ответов ночами.",
        deal_value="480 000 ₽ / год",
        initial_message="Здравствуйте! Нашим менеджерам не хватает времени обрабатывать входящие заявки 24/7.",
        objections=[
            "Боимся, что бот будет отвечать шаблонно и глупо, раздражая клиентов. VIP-клиенты не любят общаться с ботами.",
            "Что делать, если бот не поймёт вопрос клиента по нестандартному объекту?",
            "Насколько сложно обучить бота на базе наших каталогов недвижимости?",
        ],
        hints=[
            "💡 <b>Совет наставника:</b> Подчеркните вежливый тон AI и мгновенную реакцию за 3 секунды 24/7 без усталости.",
            "💡 <b>Совет наставника:</b> Заверьте в надежности мгновенной передаче диалога и уведомления менеджеру в Telegram/CRM.",
            "💡 <b>Совет наставника:</b> Предложите загрузить регламент в 1 клик и назначить демонстрацию возможностей прямо сейчас.",
        ],
    ),
    "ecommerce": GameScenario(
        id="ecommerce",
        title="E-commerce (Ритейл техники)",
        icon="🛒",
        client_persona="Михаил, коммерческий директор интернет-магазина. Нужны быстрые консультации по наличию.",
        deal_value="350 000 ₽ / год",
        initial_message="Приветствую! Покупатели часто спрашивают статус заказа и наличие товара. Бот сможет с этим помочь?",
        objections=[
            "Сможет ли бот бесшовно интегрироваться с нашей CRM и складом?",
            "Сколько дней занимает запуск системы под ключ?",
            "Готовы к внедрению. Как оформить тестовый период?",
        ],
        hints=[
            "💡 <b>Совет наставника:</b> Укажите на поддержку API-интеграций и загрузки базы знаний в 1 клик.",
            "💡 <b>Совет наставника:</b> Подчеркните быстрый старт всего за 1 день благодаря готовности AI.",
            "💡 <b>Совет наставника:</b> Сделайте финальный шаг — отправьте ссылку на тестовый период или предложите забронировать слот.",
        ],
    ),
}


def make_progress_bar(score: int, max_score: int = 100, length: int = 10) -> str:
    """Генерирует визуальный прогресс-бар [████░░░░░░]."""
    score = max(0, min(max_score, score))
    filled = round((score / max_score) * length)
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)


@dataclass
class GameSessionState:
    scenario_id: str = "b2b"
    turn: int = 1
    max_turns: int = 4
    score: int = 0
    combo: int = 0
    history: list[dict[str, str]] = field(default_factory=list)
    lead_status: str = "Холодный лид ❄️"
    client_mood: str = "😒 Скептичен"

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "turn": self.turn,
            "max_turns": self.max_turns,
            "score": self.score,
            "combo": self.combo,
            "history": self.history,
            "lead_status": self.lead_status,
            "client_mood": self.client_mood,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameSessionState:
        return cls(
            scenario_id=data.get("scenario_id", "b2b"),
            turn=data.get("turn", 1),
            max_turns=data.get("max_turns", 4),
            score=data.get("score", 0),
            combo=data.get("combo", 0),
            history=data.get("history", []),
            lead_status=data.get("lead_status", "Холодный лид ❄️"),
            client_mood=data.get("client_mood", "😒 Скептичен"),
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
            combo=0,
            history=[{"role": "client", "text": scenario.initial_message}],
            lead_status="Холодный лид ❄️",
            client_mood="😒 Скептичен",
        )
        bar = make_progress_bar(state.score)
        intro = (
            f"💎 <b>VIP ТРЕНАЖЁР ПРОДАЖ: {scenario.title}</b> {scenario.icon}\n"
            f"────────────────────────────\n"
            f"💼 <b>Потенциал сделки:</b> <code>{scenario.deal_value}</code>\n"
            f"👤 <b>Клиент:</b> {scenario.client_persona}\n\n"
            f"💬 <b>Первое сообщение клиента:</b>\n«<i>{scenario.initial_message}</i>»\n\n"
            f"📊 <b>Прогресс сделки:</b> <code>[{bar}]</code> {state.score}/100\n"
            f"🎭 <b>Настроение клиента:</b> {state.client_mood}\n"
            f"🎯 <b>Цель раунда 1/4:</b> Встретьте клиента, выявите боль и покажите экспертность!\n\n"
            f"👉 <i>Напишите ваш мощный ответ следующим сообщением!</i>"
        )
        return state, intro

    def process_turn(
        self, state: GameSessionState, user_text: str
    ) -> tuple[GameSessionState, str, bool]:
        scenario = SCENARIOS.get(state.scenario_id, SCENARIOS["b2b"])
        text = user_text.strip()

        # Анализ качества и начисление бонусов
        base_points = 15
        bonuses = []

        if len(text) > 25:
            base_points += 5
            bonuses.append("+5 Аргументация")

        if "?" in text:
            base_points += 5
            bonuses.append("+5 Квалификация (Вопрос)")

        if any(
            w in text.lower()
            for w in [
                "демо",
                "тест",
                "попробу",
                "запис",
                "созвон",
                "тариф",
                "бесплатн",
                "триал",
                "подарок",
                "скидк",
            ]
        ):
            base_points += 5
            bonuses.append("+5 Призыв к действию (CTA)")

        # Система Combo Streak
        is_strong_turn = len(bonuses) >= 2
        if is_strong_turn:
            state.combo += 1
            if state.combo >= 2:
                combo_bonus = state.combo * 2
                base_points += combo_bonus
                bonuses.append(f"+{combo_bonus} 🔥 Combo x{state.combo}")
        else:
            state.combo = 0

        turn_score = min(30, base_points)
        state.score = min(100, state.score + turn_score)
        state.history.append({"role": "user", "text": text})

        # Обновление динамического настроения и статуса лида
        if state.score >= 80:
            state.lead_status = "💎 Горячий VIP-лид (Готов подписать договор)"
            state.client_mood = "🚀 В восторге"
        elif state.score >= 50:
            state.lead_status = "🔥 Тёплый перспективный лид"
            state.client_mood = "😊 Лоялен"
        elif state.score >= 25:
            state.lead_status = "🌤 Заинтересованный лид"
            state.client_mood = "🤔 Задумчив"
        else:
            state.lead_status = "❄️ Холодный лид"
            state.client_mood = "😒 Скептичен"

        # Проверка завершения игры
        if state.turn >= state.max_turns:
            summary = self._generate_final_summary(state, scenario)
            return state, summary, True

        # Следующее возражение клиента
        objection_idx = min(state.turn - 1, len(scenario.objections) - 1)
        next_client_msg = scenario.objections[objection_idx]

        state.turn += 1
        state.history.append({"role": "client", "text": next_client_msg})

        bar = make_progress_bar(state.score)
        bonus_str = " • ".join(bonuses) if bonuses else "+15 Базовый ответ"

        reply = (
            f"⚡️ <b>Оценка хода:</b> +{turn_score} баллов! ({bonus_str})\n"
            f"────────────────────────────\n"
            f"💬 <b>Клиент ответил (Раунд {state.turn}/{state.max_turns}):</b>\n«<i>{next_client_msg}</i>»\n\n"
            f"📊 <b>Прогресс сделки:</b> <code>[{bar}]</code> {state.score}/100\n"
            f"🎭 <b>Настроение:</b> {state.client_mood} | <b>Статус:</b> {state.lead_status}\n\n"
            f"✍️ <i>Ответьте на возражение клиенту или используйте кнопку подсказки:</i>"
        )
        return state, reply, False

    def get_hint(self, state: GameSessionState) -> str:
        scenario = SCENARIOS.get(state.scenario_id, SCENARIOS["b2b"])
        hint_idx = min(state.turn - 1, len(scenario.hints) - 1)
        return scenario.hints[hint_idx]

    def _generate_final_summary(self, state: GameSessionState, scenario: GameScenario) -> str:
        score = state.score
        bar = make_progress_bar(score, length=12)

        if score >= 85:
            rank = "👑 TOP Sales Director (Пакет закрыт!)"
            conversion = "95% вероятности заключения сделки"
            badge = "🏆 Премия «Лучший закрыватель года»"
            advice = "Фантастическая работа! Вы идеально отработали боли, сняли возражения и дожали клиента на целевое действие."
        elif score >= 60:
            rank = "⭐️ Senior Sales Manager"
            conversion = "65% вероятности заключения сделки"
            badge = "🥇 Высокая конверсия"
            advice = "Отличный диалог! Клиент проявил сильный интерес. Для 100% конверсии добавляйте больше конкретики в призыве к действию."
        elif score >= 35:
            rank = "📈 Middle Seller"
            conversion = "30% вероятности заключения сделки"
            badge = "🥈 Потенциал роста"
            advice = "Хороший старт, но клиент ушел со сомнениями. Старайтесь задавать больше открытых вопросов и не бойтесь предлагать бесплатное демо."
        else:
            rank = "🌱 Intern (Стажёр)"
            conversion = "10% вероятности заключения сделки"
            badge = "🥉 Нужна практика"
            advice = "Клиент закрылся в себе. Изучите готовые скрипты продаж и используйте встроенные подсказки наставника!"

        return (
            f"🏁 <b>ИТОГИ СИМУЛЯЦИИ: {scenario.title}</b> {scenario.icon}\n"
            f"────────────────────────────\n"
            f"🎯 <b>Суммарный счет:</b> <code>[{bar}]</code> <b>{score}/100</b>\n"
            f"🎖 <b>Ваше звание:</b> {rank}\n"
            f"📊 <b>Оценка конверсии:</b> {conversion}\n"
            f"🏷 <b>Награда:</b> {badge}\n\n"
            f"💡 <b>Анализ от AI-Эксперта:</b>\n{advice}\n\n"
            f"🚀 <b>Хотите, чтобы ваш Telegram-бот сам закрывал клиентов 24/7 с такой конверсией?</b>\n"
            f"<i>Загрузите ваши регламенты и FAQ в базу знаний прямо сейчас командой /knowledge !</i>"
        )
