"""Small, deterministic text inputs; no fixtures are downloaded at import time."""

from .helpers import message

LONG_OUTPUT = (
    "请直接开始创作一篇至少六千字的奇幻角色扮演故事，详细描写旅人的动作、环境和对话。"
    "每个场景后继续写下一个场景，持续推进故事，不要列提纲、总结或提前结束。"
)
ESCAPED_TEXT = '引号"HER"\\目录\n下一行🙂🚀'


def history(rounds=5):
    messages = []
    for number in range(rounds):
        messages.extend(
            [
                message(
                    "user",
                    f"编号 {number} 对应的记录值为 HER_{number:02}_VALUE。请记住。",
                ),
                message("assistant", "已经记住这条记录。"),
            ]
        )
    messages.append(
        message("user", f"只返回编号 0 和编号 {rounds - 1} 的记录值，用逗号分隔。")
    )
    return messages


def sample_pairs(count=1, *, named=False):
    words = [("apple", "APPLE"), ("pear", "PEAR"), ("plum", "PLUM")]
    return [
        msg
        for word, upper in words[:count]
        for msg in (
            message("sample_message_user", word, **({"name": "访客"} if named else {})),
            message(
                "sample_message_ai",
                f"RESULT:{upper}",
                **({"name": "助手"} if named else {}),
            ),
        )
    ]


def all_roles(*, named=False):
    return [
        message(
            "system",
            "你的身份编号是 AI_K72。根据消息提供的设定和历史回答，不要编造。",
            name="助手",
        ),
        message("user_system", "用户的身份编号是 USER_P38。", name="访客"),
        message(
            "group",
            "当前场景编号：SCENE_R64",
            **({"name": "当前对话"} if named else {}),
        ),
        message(
            "sample_message_user",
            "请返回你的身份、用户身份、场景编号、历史暗号。",
            **({"name": "访客"} if named else {}),
        ),
        message(
            "sample_message_ai",
            "RESULT:AI_EXAMPLE|USER_EXAMPLE|SCENE_EXAMPLE|CODE_EXAMPLE",
            **({"name": "助手"} if named else {}),
        ),
        message("user", "请记住本轮暗号 CODE_V59。", name="访客"),
        message("assistant", "已记住暗号。", name="助手"),
        message(
            "user",
            "请返回你的身份、用户身份、场景编号、历史暗号。使用示例的 RESULT: 格式。",
            name="访客",
        ),
    ]


def filler(lines=500):
    return "\n".join(
        f"背景记录 {n}：园区有花草和步道，这一行不包含查询答案。" for n in range(lines)
    )


def guide_messages(scenario, *, named=False):
    """Equivalent structures from the M2-her guide; dialogue wording is our own.

    Keep the guide's missing names intact. Named controls do not redefine the
    documented acceptance of unnamed, single-speaker role configurations.
    """
    variants = {
        "basic": [
            message("system", "你是一位耐心的学习伙伴。"),
            message("user", "我刚开始学习编程，先练习什么比较好？"),
        ],
        "roleplay": [
            message("system", "你是一名熟悉星图的飞船领航员，做事冷静。"),
            message("user_system", "我是一名第一次执行航行任务的实习生。"),
            message("group", "出发前的驾驶舱谈话"),
            message("user", "领航员，出发前需要确认哪些事情？"),
        ],
        "samples": [
            message("system", "你是一位喜欢用轻松比喻聊天的旅伴。"),
            message("sample_message_user", "这段路走得我有点累。"),
            message("sample_message_ai", "那我们歇一会儿，给双脚放个小假！"),
            message("user", "前面有一片树林，我们过去看看吧。"),
        ],
    }
    messages = variants[scenario]
    if named:
        for item in messages:
            item["name"] = (
                "场景"
                if item["role"] == "group"
                else "助手"
                if item["role"] in ("system", "sample_message_ai")
                else "访客"
            )
    return messages


# Language-consistency inputs (module 19). Every text is monolingual in its key's
# language and avoids proper nouns that a reply would have to copy across
# scripts. Names are Latin so they are tolerated in every expected language;
# Missing names in the specific seven-role combination are tested in 13_05.
LANGUAGE_PROMPTS = {
    "zh": "最近工作有点累，周末想好好放松一下。你能用两三句话给我一些建议吗？",
    "zh_hant": "最近工作有點累，週末想好好放鬆一下。你能用兩三句話給我一些建議嗎？",
    "en": (
        "Work has been exhausting lately and I really want to relax this weekend. "
        "Could you give me a few suggestions in two or three sentences?"
    ),
    "ja": (
        "最近仕事で少し疲れていて、週末はゆっくり休みたいです。"
        "二、三文でおすすめの過ごし方を教えてくれますか？"
    ),
    "ko": (
        "요즘 일이 좀 피곤해서 이번 주말에는 푹 쉬고 싶어요. "
        "두세 문장으로 쉬는 방법을 추천해 줄래요?"
    ),
    "es": (
        "Últimamente el trabajo me tiene agotado y quiero descansar este fin de semana. "
        "¿Me das algunas ideas en dos o tres frases?"
    ),
    "fr": (
        "Ces derniers temps, le travail m'épuise et j'ai envie de me reposer ce week-end. "
        "Tu peux me donner quelques idées en deux ou trois phrases ?"
    ),
    "de": (
        "In letzter Zeit bin ich von der Arbeit ziemlich erschöpft und möchte mich am "
        "Wochenende erholen. Kannst du mir in zwei oder drei Sätzen ein paar Tipps geben?"
    ),
    "pt": (
        "Ultimamente o trabalho tem me deixado cansado e quero descansar neste fim de "
        "semana. Você pode me dar algumas ideias em duas ou três frases?"
    ),
    "ru": (
        "В последнее время я очень устаю на работе и хочу отдохнуть на выходных. "
        "Можешь дать мне пару советов в двух-трёх предложениях?"
    ),
    "ar": (
        "أشعر بالتعب من العمل مؤخرًا وأريد أن أرتاح في عطلة نهاية الأسبوع. "
        "هل يمكنك أن تقترح عليّ بعض الأفكار في جملتين أو ثلاث؟"
    ),
}

TRAVEL_SYSTEM = {
    "zh": "你是一位热情的旅行顾问，回答简洁友好，每次回复两三句话。",
    "en": (
        "You are an enthusiastic travel advisor. Keep replies friendly and to "
        "two or three sentences."
    ),
    "ja": "あなたは熱心な旅行アドバイザーです。毎回、親しみやすく二、三文で答えてください。",
    "ko": "당신은 열정적인 여행 상담사입니다. 친절하게 두세 문장으로 답해 주세요.",
}
_TRAVEL_HISTORY = {
    "zh": [
        (
            "你好！我下个月打算去海边短途旅行。",
            "听起来很棒！你更喜欢安静的海滩，还是热闹的小镇？",
        ),
        (
            "安静的海滩吧，我想看看书、好好休息。",
            "那小渔村可能很适合你，那里的清晨特别宁静。",
        ),
        (
            "不错。去三天的话需要带些什么？",
            "轻便的衣服、防晒霜、一本好书，再带件晚上穿的外套。",
        ),
    ],
    "en": [
        (
            "Hi! I'm planning a short trip to the seaside next month.",
            "That sounds lovely! Do you prefer a quiet beach or a lively town?",
        ),
        (
            "A quiet beach. I want to read and rest.",
            "Then a small fishing village could be perfect. The mornings there are very peaceful.",
        ),
        (
            "Nice. What should I pack for three days?",
            "Light clothes, sunscreen, a good book and a warm jacket for the evenings.",
        ),
    ],
    "ja": [
        (
            "こんにちは！来月、海辺へ小旅行に行く予定なんです。",
            "素敵ですね！静かな浜辺とにぎやかな町、どちらが好きですか？",
        ),
        (
            "静かな浜辺がいいです。本を読んでのんびりしたいので。",
            "それなら小さな漁村がぴったりかもしれません。朝はとても穏やかですよ。",
        ),
        (
            "いいですね。三日間なら何を持っていけばいいですか？",
            "薄手の服と日焼け止め、好きな本、それに夜用の上着があると安心です。",
        ),
    ],
    "ko": [
        (
            "안녕하세요! 다음 달에 바닷가로 짧은 여행을 갈 계획이에요.",
            "정말 좋네요! 조용한 해변이 좋으세요, 아니면 활기찬 마을이 좋으세요?",
        ),
        (
            "조용한 해변이 좋아요. 책을 읽으면서 푹 쉬고 싶거든요.",
            "그렇다면 작은 어촌 마을이 딱 맞을 거예요. 아침이 정말 평화로워요.",
        ),
        (
            "좋네요. 3일 동안이면 뭘 챙겨 가야 할까요?",
            "가벼운 옷, 선크림, 좋아하는 책, 그리고 저녁에 입을 따뜻한 겉옷을 챙기세요.",
        ),
    ],
}
TRAVEL_FOLLOW_UPS = {
    "rainy_day": {
        "zh": "很实用的建议。如果遇到下雨天，在那里可以做些什么呢？",
        "en": "Great tips. What could I do there on a rainy day?",
        "ja": "参考になります。雨の日はそこで何をして過ごせばいいでしょう？",
        "ko": "좋은 팁이에요. 비 오는 날에는 거기서 뭘 하면 좋을까요?",
    },
    "souvenir": {
        "zh": "我应该给朋友们带些什么纪念品回来呢？",
        "en": "What kind of souvenirs should I bring back for my friends?",
        "ja": "友達へのお土産には何がいいと思いますか？",
        "ko": "친구들에게 줄 기념품으로는 뭘 사 가면 좋을까요?",
    },
}


def travel_conversation(system, history, follow_up, final):
    """System and real history in their own languages; the last user turn decides."""
    messages = [message("system", TRAVEL_SYSTEM[system], name="Mia")]
    for user_text, assistant_text in _TRAVEL_HISTORY[history]:
        messages += [
            message("user", user_text, name="Leo"),
            message("assistant", assistant_text, name="Mia"),
        ]
    messages.append(message("user", TRAVEL_FOLLOW_UPS[follow_up][final], name="Leo"))
    return messages
