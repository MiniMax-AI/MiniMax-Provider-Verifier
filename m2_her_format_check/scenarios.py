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
# this deployment rejects unnamed advanced roles, which is tested in 13_05.
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

_CAFE_PERSONA = {
    "zh": (
        "你是一位温柔细心的咖啡店店主，说话亲切自然，喜欢关心客人。",
        "用户是店里的常客，最近工作很忙。",
        "午后安静的咖啡店",
        "今天有什么推荐吗？",
        "欢迎回来！今天想喝点热的还是冰的？",
    ),
    "en": (
        "You are a gentle and attentive coffee shop owner who speaks warmly "
        "and cares about your customers.",
        "The user is a regular customer who has been very busy with work lately.",
        "A quiet coffee shop in the afternoon",
        "Anything you would recommend today?",
        "Welcome back! Would you like something hot or iced today?",
    ),
    "ja": (
        "あなたは優しくて気配りのできるカフェの店主です。"
        "親しみやすい口調で話し、いつもお客さんのことを気にかけています。",
        "ユーザーはこの店の常連客で、最近は仕事がとても忙しいようです。",
        "午後の静かなカフェ",
        "今日のおすすめは何ですか？",
        "おかえりなさい！今日は温かい飲み物と冷たい飲み物、どちらにしますか？",
    ),
    "ko": (
        "당신은 다정하고 세심한 카페 사장님입니다. "
        "친근하게 말하며 언제나 손님을 챙깁니다.",
        "사용자는 이 카페의 단골손님이며 요즘 일이 무척 바쁩니다.",
        "오후의 조용한 카페",
        "오늘은 뭘 추천해 주실래요?",
        "다시 오셨네요! 오늘은 따뜻한 음료가 좋으세요, 시원한 음료가 좋으세요?",
    ),
    "es": (
        "Eres la dueña amable y atenta de una cafetería. Hablas con calidez "
        "y siempre te preocupas por tus clientes.",
        "El usuario es un cliente habitual que últimamente tiene mucho trabajo.",
        "Una cafetería tranquila por la tarde",
        "¿Qué me recomiendas para tomar hoy?",
        "¡Bienvenido de nuevo! ¿Hoy te apetece algo caliente o algo frío?",
    ),
}
CAFE_QUESTIONS = {
    "zh": "刚开完一个很长的会，累坏了。点什么能让我稍微打起精神？",
    "en": (
        "I just finished a long meeting and I'm exhausted. "
        "What should I order to feel a little better?"
    ),
    "ja": "長い会議がやっと終わって、くたくたです。少し元気が出る飲み物は何がいいですか？",
    "ko": "긴 회의가 이제 막 끝나서 너무 지쳤어요. 기분이 좀 나아지려면 뭘 주문하면 좋을까요?",
    "es": (
        "Acabo de salir de una reunión larguísima y estoy agotado. "
        "¿Qué me recomiendas pedir para sentirme mejor?"
    ),
}


def cafe_roleplay(persona, question):
    """Seven-role structure written in one language, then a user turn in another."""
    system, user_system, group, sample_user, sample_ai = _CAFE_PERSONA[persona]
    return [
        message("system", system, name="Mia"),
        message("user_system", user_system, name="Leo"),
        message("group", group, name="Cafe"),
        message("sample_message_user", sample_user, name="Leo"),
        message("sample_message_ai", sample_ai, name="Mia"),
        message("user", CAFE_QUESTIONS[question], name="Leo"),
    ]


LANGUAGE_INSTRUCTIONS = {
    # variant: (system or None, user text, language of both texts, required reply).
    # The instruction is written in the user's language and asks for another one.
    "system_en_user_zh": (
        "你是一位英语口语陪练伙伴。无论用户使用什么语言，你都只用英语回复。",
        "我明天要参加面试，有点紧张，你能鼓励我一下吗？",
        "zh",
        "en",
    ),
    "system_ja_user_en": (
        "You are a friendly Japanese conversation partner. Always reply only in "
        "Japanese, whatever language the user writes in.",
        "I have a job interview tomorrow and I'm a little nervous. Could you cheer me up?",
        "en",
        "ja",
    ),
    "system_zh_user_ko": (
        "당신은 중국어 회화 연습 파트너입니다. 사용자가 어떤 언어로 말하든 "
        "반드시 중국어로만 답하세요.",
        "내일 면접이 있어서 좀 긴장돼요. 응원 한마디 해 줄래요?",
        "ko",
        "zh",
    ),
    "system_ko_user_ja": (
        "あなたは韓国語の会話練習パートナーです。ユーザーが何語で話しても、"
        "必ず韓国語だけで返事をしてください。",
        "明日面接があって、少し緊張しています。励ましてもらえますか？",
        "ja",
        "ko",
    ),
    "user_request_ko": (
        None,
        "请只用韩语回答我：明天要面试了，我有点紧张，你能鼓励我一下吗？",
        "zh",
        "ko",
    ),
    "user_request_ja": (
        None,
        "Please answer only in Japanese: I have a job interview tomorrow and I'm "
        "a little nervous. Could you cheer me up?",
        "en",
        "ja",
    ),
    "user_request_zh": (
        None,
        "中国語だけで答えてください。明日面接があって、少し緊張しています。"
        "励ましてもらえますか？",
        "ja",
        "zh",
    ),
    "user_request_en": (
        None,
        "영어로만 대답해 주세요. 내일 면접이 있어서 좀 긴장돼요. 응원 한마디 해 줄래요?",
        "ko",
        "en",
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
