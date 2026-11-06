"""Deterministic reply-language checks for the M2-her language-consistency cases.

The rules are mechanical and offline: Unicode script runs, small character sets
that separate Simplified/Traditional Chinese and Chinese/Japanese, and
function-word lexicons for Latin-script languages. No model, network or
third-party detector is used. Judgment rules are summarized in README.md.

Language consistency is a behavior target for a chat model, not an API format
guarantee; callers mark these cases as behavior evaluations.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

LANGUAGES = {
    "zh": "Simplified Chinese",
    "zh_hant": "Traditional Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
}
LATIN_LANGUAGES = ("en", "es", "fr", "de", "pt")
# Scripts counted per character; alphabetic scripts are counted per word run.
PER_CHARACTER = {"han", "kana", "hangul"}
SCRIPTS = ("han", "kana", "hangul", "latin", "cyrillic", "arabic", "other")
NATIVE = {
    "zh": {"han"},
    "zh_hant": {"han"},
    "ja": {"han", "kana"},
    "ko": {"hangul"},
    "ru": {"cyrillic"},
    "ar": {"arabic"},
    **{language: {"latin"} for language in LATIN_LANGUAGES},
}
# Latin loanwords (names, OK, Python) are tolerated inside other languages;
# whole Latin sentences are caught by the segment rule instead.
FORBIDDEN = {
    language: set(SCRIPTS) - {"latin"} - native for language, native in NATIVE.items()
}

# Pairs whose simplified form is not standard Traditional text and vice versa.
_VARIANT_PAIRS = (  # noqa: SIM905 - keep each visual pair together in compact rows
    "们們 这這 说說 吗嗎 还還 时時 对對 为為 么麼 发發 开開 长長 门門 问問 间間 东東 "
    "车車 头頭 见見 觉覺 让讓 话話 语語 认認 识識 应應 该該 关關 实實 现現 样樣 从從 "
    "经經 过過 进進 动動 边邊 电電 题題 欢歡 乐樂 爱愛 谢謝 请請 网網 线線 书書 买買 "
    "卖賣 钱錢 难難 备備 飞飛 马馬 鸟鳥 鱼魚 龙龍 会會 来來 学學 点點 个個 没沒 给給 "
    "气氣 体體 轻輕 运運 灵靈 视視 听聽 写寫 读讀 岁歲 钟鐘 "
    # Everyday replies (e.g. travel or leisure advice) often avoid the pairs
    # above, which made plain Simplified text inconclusive in live runs.
    "馆館 当當 国國 场場 处處 务務 带帶 业業 两兩 严嚴 丽麗 习習 乡鄉 亲親 "
    "众眾 优優 传傳 伤傷 价價 儿兒 农農 军軍 办辦 华華 单單 卫衛 压壓 厅廳 "
    "县縣 变變 员員 园園 图圖 圆圓 团團 宁寧 导導 层層 岛島 币幣 师師 帮幫 "
    "广廣 庆慶 张張 录錄 总總 战戰 报報 护護 择擇 换換 显顯 杂雜 权權 极極 "
    "构構 标標 树樹 桥橋 检檢 汤湯 济濟 热熱 爷爺 环環 疗療 盘盤 确確 种種 "
    "积積 称稱 笔筆 类類 红紅 级級 纸紙 练練 组組 细細 终終 结結 统統 继繼 "
    "续續 绿綠 罗羅 职職 联聯 脑腦 节節 药藥 获獲 虽雖 规規 观觀 讲講 记記 "
    "许許 论論 设設 证證 评評 试試 详詳 课課 调調 谈談 贵貴 费費 资資 赛賽 "
    "选選 遗遺 邮郵 铁鐵 银銀 错錯 闭閉 队隊 阳陽 际際 陆陸 页頁 顺順 风風 "
    "饭飯 饮飲 驾駕 验驗 鲜鮮 鸡雞 举舉"
).split()
SIMPLIFIED_ONLY = frozenset(pair[0] for pair in _VARIANT_PAIRS)
TRADITIONAL_ONLY = frozenset(pair[1] for pair in _VARIANT_PAIRS)
# Chinese characters that do not occur in standard Japanese text. Simplified
# forms shared with Japanese shinjitai (会 来 学 点 写 体 属 没 …) are excluded.
CHINESE_NOT_JAPANESE = (SIMPLIFIED_ONLY - set("会来学点写体没个当国")) | frozenset(
    "你她很呢吧啊嗯哦呀嘛"
)
VARIANT_TOLERANCE = 0.1
JAPANESE_MIN_KANA_RATIO = 0.2
JAPANESE_HAN_ONLY_SEGMENT = 5
FOREIGN_LATIN_SEGMENT_WORDS = 3
LATIN_SEGMENT_WORDS = 4

_LEXICON = {
    "en": """
        the and you your you're you'll you've i'm i'll i've it's it'll that's there's
        don't can't won't let's is are was were have has had this that these those with what
        would could should just about really there here they them their some maybe sounds
        feel little something today weekend enjoy relax good great nice hello hey thanks
        thank how why when which for from of to it my me we be do if or an at by our
        so in on am man no son sure okay yes please sorry love like time get make take try
        need want know think help best better more very too also all any every after before
        into out up than then she he his her him who where been being doing going
        walk outdoors stretch gently sleep stroll breathe breathing spend relaxing
    """,
    "es": """
        el los las del al y una unos unas es está están estás estoy soy eres son muy pero
        más mucho mucha también porque cuando donde dónde qué cómo cuál hola gracias hoy
        aquí ahí algo nada todo bien bueno buena puedes quieres tienes tengo hay vamos día
        tiempo fin semana con sin por para lo le les se te me mi tu tus su sus yo nosotros
        claro así ya entonces ahora esto eso este esta ese esa un de la que en no nos como
        mal descansar relajarte tranquilo puede ayudarte
    """,
    "fr": """
        le la les des du de et est je tu vous nous il elle on un une que qui pas ne pour
        avec dans sur mon ma mes ta tes ce cette ces ça c'est très mais aujourd'hui bonjour
        salut merci oui suis es êtes sont fait peux peut veux comme moi toi bien fin son se
        te me en au aux j'ai quelque chose peu temps journée idée idées essayer pourquoi
        quand où voici aussi encore alors être avoir hier
    """,
    "de": """
        der die das und ist ich du nicht ein eine einen zu mit es sie wir ihr mein meine dein
        deine auf für heute wie was sehr aber auch bin bist sind den dem des hallo danke ja
        nein gut schön wochenende zeit etwas kannst kann möchtest willst mal noch oder so in
        hast habe dich mich dir mir uns euch dass wenn weil vielleicht einfach bisschen gerne
        gern machen entspannen ruhig warum wann wo hier jetzt dann schon immer im am vom zum
        zur ins sich man viel viele mehr nach da um
    """,
    "pt": """
        você vocês não é um uma uns umas eu meu minha seu sua nosso muito muita mas mais hoje
        olá oi obrigado obrigada também está estás estou sou são do da dos das em no na nos
        nas isso isto esse essa este esta aqui como bem bom boa fim semana tempo algo nada
        tudo todo pode podemos quer vamos dia porque quando onde com sem por para que de se
        te me já ainda então agora assim claro ótimo ótima legal coisa pouco tem tenho fazer
        ao aos às pela pelo lhe num numa ser ter ir mal descansar
    """,
}
_CHARACTER_MARKERS = {
    "es": "ñ¿¡",
    "pt": "ãõ",
    "de": "ßäöü",
    "fr": "œèëîïûù",
}


def _owners(groups):
    seen = Counter(item for items in groups.values() for item in set(items))
    return {
        item: language
        for language, items in groups.items()
        for item in items
        if seen[item] == 1
    }


# Words shared by several lexicons are not evidence for any one language.
WORD_OWNER = _owners({k: v.split() for k, v in _LEXICON.items()})
CHARACTER_OWNER = _owners({k: list(v) for k, v in _CHARACTER_MARKERS.items()})
_ELISION = re.compile(r"^(?:qu|[ldjcnsmt])'[^\W\d_]")
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")
_SEGMENT_BREAK = re.compile(
    r"[。！？!?；;…\n\r（）()\[\]【】「」『』《》“”\"*]+|\.(?:\s+|$)"
)


def script_of(character: str) -> str | None:
    """Return the script of one letter; marks, digits, punctuation and emoji are None."""
    if not character.isalpha():
        return None
    point = ord(character)
    if (
        0x3040 <= point <= 0x30FF
        or 0x31F0 <= point <= 0x31FF
        or 0xFF66 <= point <= 0xFF9D
    ):
        return "kana"
    if (
        0x3400 <= point <= 0x4DBF
        or 0x4E00 <= point <= 0x9FFF
        or 0xF900 <= point <= 0xFAFF
        or 0x20000 <= point <= 0x3134F
        or point in (0x3005, 0x3006)
    ):
        return "han"
    if (
        0xAC00 <= point <= 0xD7AF
        or 0x1100 <= point <= 0x11FF
        or 0x3130 <= point <= 0x318F
        or 0xA960 <= point <= 0xA97F
        or 0xD7B0 <= point <= 0xD7FF
    ):
        return "hangul"
    if point <= 0x024F or 0x1E00 <= point <= 0x1EFF or 0xFF21 <= point <= 0xFF5A:
        return "latin"
    if 0x0400 <= point <= 0x052F:
        return "cyrillic"
    if (
        0x0600 <= point <= 0x06FF
        or 0x0750 <= point <= 0x077F
        or 0x08A0 <= point <= 0x08FF
        or 0xFB50 <= point <= 0xFDFF
        or 0xFE70 <= point <= 0xFEFF
    ):
        return "arabic"
    return "other"


def script_runs(text: str) -> list[tuple[str, str]]:
    """Maximal same-script letter runs; combining marks stay with their base letter.

    A lone kana/Han/Cyrillic letter surrounded by non-letters is emoticon-like
    (``Σ(っ°Д°;)っ``, ``(￣口￣)``) and is ignored. Letters inside words, such
    as the particle in ``本を読む``, are kept.
    """
    runs = []
    for word in _words(unicodedata.normalize("NFC", text)):
        if sum(map(_letters, (run for _, run in word))) == 1 and word[0][0] in (
            "kana",
            "han",
            "cyrillic",
            "other",
        ):
            continue
        runs.extend(word)
    return runs


def _words(text: str) -> list[list[tuple[str, str]]]:
    words, runs, current, letters = [], [], None, []
    for character in text + " ":
        if letters and unicodedata.category(character).startswith("M"):
            letters.append(character)
            continue
        script = script_of(character)
        if script != current and letters:
            runs.append((current, "".join(letters)))
            letters = []
        if script is None and runs:
            words.append(runs)
            runs = []
        current = script
        if script is not None:
            letters.append(character)
    return words


def _letters(run: str) -> int:
    return sum(not unicodedata.category(c).startswith("M") for c in run)


def script_units(text: str) -> Counter:
    """Comparable size per script: CJK characters, or alphabetic word runs."""
    units = Counter()
    for script, run in script_runs(text):
        units[script] += _letters(run) if script in PER_CHARACTER else 1
    return units


def latin_scores(text: str) -> Counter:
    """Count language-specific function words and diacritics, never shared ones."""
    lowered = unicodedata.normalize("NFC", text).lower().replace("’", "'")
    scores = Counter()
    for token in _WORD.findall(lowered):
        if any(script_of(c) != "latin" for c in token if c != "'"):
            continue
        if token in WORD_OWNER:
            scores[WORD_OWNER[token]] += 1
        elif _ELISION.match(token):
            scores["fr"] += 1
    for character in lowered:
        if character in CHARACTER_OWNER:
            scores[CHARACTER_OWNER[character]] += 1
    return scores


def latin_language(text: str) -> str | None:
    scores = latin_scores(text)
    if not scores:
        return None
    ranked = scores.most_common(2)
    if ranked[0][1] < 2 or (len(ranked) == 2 and ranked[0][1] == ranked[1][1]):
        return None
    return ranked[0][0]


def chinese_variant(text: str) -> str | None:
    simplified = sum(c in SIMPLIFIED_ONLY for c in text)
    traditional = sum(c in TRADITIONAL_ONLY for c in text)
    if simplified == traditional:
        return None
    return "zh" if simplified > traditional else "zh_hant"


# A writing system alone cannot distinguish Russian from Ukrainian, or
# Arabic from Persian. Require positive lexical evidence on the shared script.
_SCRIPT_LANGUAGE_WORDS = {
    "ru": (
        "это что чтобы можно можете если выходных отдохнуть "
        "хорошо себя немного лучше пусть хотя просто попробуй попробуйте "
        "погулять проведите уделите время очень будет"
    ),
    "ar": (
        "في على إلى أن هذا هذه يمكنك يمكن بعض ثم أو عن "
        "التي الذي حاول جرب عطلة نهاية الأسبوع أنشطة الاسترخاء الراحة "
        "قليلا مثلا نفسك خلال"
    ),
}
# Common letters in neighboring languages that are absent from standard
# Russian / Arabic. This rejects a positive contradiction even in mixed text.
_NON_TARGET_LETTERS = {"ru": set("іїєґўљњџђћѓќј"), "ar": set("پچژگکیٹڈڑںے")}


def classify(text: str) -> str | None:
    """Dominant language of a span; None when no comparable letters are present.

    Latin text without distinctive function words returns ``latin``. Han text
    without variant markers stays inconclusive for the Chinese variant.
    """
    units = script_units(text)
    han, kana = units["han"], units["kana"]
    weights = {}
    if han + kana:
        if kana / (han + kana) >= JAPANESE_MIN_KANA_RATIO:
            weights["ja"] = han + kana
        else:
            weights[chinese_variant(text) or "han"] = han + kana
    if units["hangul"]:
        weights["ko"] = units["hangul"]
    for script, language in (("cyrillic", "ru"), ("arabic", "ar")):
        if units[script]:
            # Arabic short vowels are optional combining marks within words.
            unmarked = "".join(
                c for c in text.casefold() if not unicodedata.combining(c)
            )
            words = set(_WORD.findall(unmarked))
            matches = words.intersection(_SCRIPT_LANGUAGE_WORDS[language].split())
            weights[language if len(matches) >= 2 else script] = units[script]
    if units["other"]:
        weights["other"] = units["other"]
    if units["latin"]:
        weights[latin_language(text) or "latin"] = units["latin"]
    if not weights:
        return None
    return max(weights, key=weights.get)


@dataclass
class LanguageReport:
    expected: str
    detected: str | None
    units: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.problems:
            return "mismatch"
        return "match" if self.detected == self.expected else "uncertain"

    @property
    def ok(self) -> bool:
        return self.verdict == "match"

    def summary(self) -> str:
        return (
            f"expected {self.expected} ({LANGUAGES[self.expected]}), detected "
            f"{self.detected}; verdict={self.verdict}; units={self.units}; problems={self.problems}"
        )


def language_report(text: str, expected: str) -> LanguageReport:
    """Check that a reply is in one expected language without foreign spans."""
    if expected not in LANGUAGES:
        raise ValueError(f"unsupported language {expected!r}; use {sorted(LANGUAGES)}")
    text = unicodedata.normalize("NFC", text)
    units = script_units(text)
    detected = classify(text)
    report = LanguageReport(
        expected, detected, {k: v for k, v in units.items() if k in SCRIPTS}
    )
    problems = report.problems
    if detected is None:
        if not any(character.isalpha() for character in text):
            problems.append("no letters to identify a language")
        return report
    # Weak evidence in an otherwise compatible script is inconclusive, not a
    # language mismatch. Foreign scripts/words below still override uncertainty.
    if detected != expected and detected not in NATIVE[expected]:
        problems.append(f"dominant language is {detected}, not {expected}")
    foreign_letters = sorted(
        set(text.casefold()) & _NON_TARGET_LETTERS.get(expected, set())
    )
    if foreign_letters:
        problems.append(f"non-{expected} letters: {foreign_letters}")
    for script in sorted(FORBIDDEN[expected]):
        spans = [
            run for s, run in script_runs(text) if s == script and _letters(run) >= 2
        ]
        if spans:
            problems.append(f"{script} text in a {expected} reply: {spans[:3]}")
    if expected in ("zh", "zh_hant"):
        own, other = (
            (SIMPLIFIED_ONLY, TRADITIONAL_ONLY)
            if expected == "zh"
            else (TRADITIONAL_ONLY, SIMPLIFIED_ONLY)
        )
        own_count = sum(c in own for c in text)
        mixed = [c for c in text if c in other]
        if mixed and len(mixed) > VARIANT_TOLERANCE * (own_count + len(mixed)):
            problems.append(
                f"mixed Chinese variant: {len(mixed)} opposite-variant vs "
                f"{own_count} expected-variant characters {sorted(set(mixed))[:8]}"
            )
    if expected == "ja":
        markers = sorted({c for c in text if c in CHINESE_NOT_JAPANESE})
        if markers:
            problems.append(f"Chinese-only characters in a Japanese reply: {markers}")
    for segment in filter(str.strip, _SEGMENT_BREAK.split(text)):
        problem = _segment_problem(segment.strip(), expected)
        if problem:
            problems.append(problem)
    return report


def _segment_problem(segment: str, expected: str) -> str | None:
    units = script_units(segment)
    latin = units["latin"]
    others = sum(units[s] for s in SCRIPTS if s != "latin")
    if (
        expected == "ja"
        and units["han"] >= JAPANESE_HAN_ONLY_SEGMENT
        and not units["kana"]
    ):
        return f"Han-only segment without kana (likely Chinese): {segment!r}"
    if expected not in LATIN_LANGUAGES:
        if latin >= FOREIGN_LATIN_SEGMENT_WORDS and latin > others:
            return f"Latin-script sentence in a {expected} reply: {segment!r}"
        return None
    if latin < LATIN_SEGMENT_WORDS or others:
        return None
    scores = latin_scores(segment)
    best, score = (scores.most_common(1) or [(None, 0)])[0]
    if best not in (None, expected) and score >= 2 and score > scores[expected]:
        return f"{best} sentence in a {expected} reply: {segment!r}"
    return None
