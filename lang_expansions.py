"""ORBITRA — multilingual query expansion dictionaries.

Each language dict maps English sport/concept terms → translated terms.
Used by expand_queries() to build native-language search variants.
"""

# ── Sport/activity terms ────────────────────────────────────────────────────

SPORT_ZH = {  # Mandarin Chinese (Simplified)
    "basketball": "篮球", "football": "足球", "soccer": "足球",
    "golf": "高尔夫", "tennis": "网球", "swimming": "游泳",
    "badminton": "羽毛球", "volleyball": "排球", "baseball": "棒球",
    "rugby": "橄榄球", "cricket": "板球", "athletics": "田径",
    "cycling": "骑行", "martial arts": "武术", "gymnastics": "体操",
    "skiing": "滑雪", "ice hockey": "冰球", "climbing": "攀岩",
    "triathlon": "铁人三项",
}

GENERAL_ZH = {  # Mandarin Chinese (Simplified)
    "summer camp": "夏令营", "travel agency": "旅行社",
    "camp": "夏令营", "tour": "旅游", "training": "培训",
    "academy": "学院", "school": "学校", "program": "项目",
    "reseller": "代理商", "operator": "运营商", "agent": "代理",
    "package": "套餐", "facility": "设施", "club": "俱乐部",
    "coaching": "教练", "youth": "青少年", "junior": "青年",
    "international": "国际", "overseas": "海外", "abroad": "出境",
    "booking": "预订", "price": "价格", "contact": "联系",
}

REGION_ZH = {  # Place names in Chinese
    "thailand": "泰国", "bangkok": "曼谷", "chiang mai": "清迈",
    "phuket": "普吉岛",
    "singapore": "新加坡", "malaysia": "马来西亚", "kuala lumpur": "吉隆坡",
    "vietnam": "越南", "ho chi minh": "胡志明市", "hanoi": "河内",
    "indonesia": "印度尼西亚", "jakarta": "雅加达", "bali": "巴厘岛",
    "philippines": "菲律宾", "manila": "马尼拉", "myanmar": "缅甸",
    "cambodia": "柬埔寨", "southeast asia": "东南亚",
    "hong kong": "香港", "macau": "澳门", "taiwan": "台湾",
    "beijing": "北京", "shanghai": "上海", "china": "中国",
    "japan": "日本", "korea": "韩国", "usa": "美国",
    "europe": "欧洲", "australia": "澳大利亚",
}

SPORT_ZH_TW = {  # Traditional Chinese (Taiwan / HK)
    "basketball": "籃球", "football": "足球", "golf": "高爾夫",
    "tennis": "網球", "swimming": "游泳", "volleyball": "排球",
    "camp": "夏令營", "academy": "學院", "training": "培訓",
    "school": "學校", "travel agency": "旅行社", "summer camp": "夏令營",
    "club": "俱樂部", "youth": "青少年", "coaching": "教練",
}

SPORT_JA = {  # Japanese
    "basketball": "バスケットボール", "football": "フットボール",
    "soccer": "サッカー", "golf": "ゴルフ", "tennis": "テニス",
    "swimming": "水泳", "baseball": "野球", "volleyball": "バレーボール",
    "badminton": "バドミントン", "rugby": "ラグビー",
    "camp": "キャンプ", "academy": "アカデミー", "training": "トレーニング",
    "school": "スクール", "summer camp": "サマーキャンプ",
    "travel agency": "旅行代理店", "tour": "ツアー", "club": "クラブ",
    "youth": "ユース", "junior": "ジュニア",
}

SPORT_KO = {  # Korean
    "basketball": "농구", "football": "축구", "soccer": "축구",
    "golf": "골프", "tennis": "테니스", "swimming": "수영",
    "baseball": "야구", "volleyball": "배구", "badminton": "배드민턴",
    "camp": "캠프", "academy": "아카데미", "training": "트레이닝",
    "school": "스쿨", "summer camp": "여름캠프",
    "travel agency": "여행사", "tour": "투어", "club": "클럽",
    "youth": "유스", "junior": "주니어",
}

SPORT_DE = {  # German
    "basketball": "Basketball", "football": "Fußball", "soccer": "Fußball",
    "golf": "Golf", "tennis": "Tennis", "swimming": "Schwimmen",
    "volleyball": "Volleyball", "badminton": "Badminton", "rugby": "Rugby",
    "camp": "Camp", "summer camp": "Sommercamp", "academy": "Akademie",
    "school": "Schule", "training": "Training", "club": "Verein",
    "travel agency": "Reisebüro", "tour": "Tour",
    "youth": "Jugend", "junior": "Junior", "coaching": "Coaching",
    "facility": "Einrichtung", "program": "Programm",
}

SPORT_NL = {  # Dutch
    "basketball": "basketbal", "football": "voetbal", "soccer": "voetbal",
    "golf": "golf", "tennis": "tennis", "swimming": "zwemmen",
    "volleyball": "volleybal", "badminton": "badminton", "rugby": "rugby",
    "camp": "kamp", "summer camp": "zomerkamp", "academy": "academie",
    "school": "school", "training": "training", "club": "club",
    "travel agency": "reisbureau", "tour": "tour",
    "youth": "jeugd", "junior": "junior", "coaching": "coaching",
    "facility": "faciliteit", "program": "programma",
}

SPORT_FR = {  # French
    "basketball": "basketball", "football": "football", "soccer": "football",
    "golf": "golf", "tennis": "tennis", "swimming": "natation",
    "volleyball": "volleyball", "badminton": "badminton", "rugby": "rugby",
    "camp": "camp", "summer camp": "camp d'été", "academy": "académie",
    "school": "école", "training": "entraînement", "club": "club",
    "travel agency": "agence de voyage", "tour": "circuit",
    "youth": "jeune", "junior": "junior", "coaching": "coaching",
    "facility": "installation", "program": "programme",
}

SPORT_ES = {  # Spanish
    "basketball": "baloncesto", "football": "fútbol", "soccer": "fútbol",
    "golf": "golf", "tennis": "tenis", "swimming": "natación",
    "volleyball": "voleibol", "badminton": "bádminton", "rugby": "rugby",
    "camp": "campamento", "summer camp": "campamento de verano",
    "academy": "academia", "school": "escuela", "training": "entrenamiento",
    "club": "club", "travel agency": "agencia de viajes", "tour": "tour",
    "youth": "jóvenes", "junior": "junior", "coaching": "entrenamiento",
    "facility": "instalación", "program": "programa",
}

SPORT_PT = {  # Portuguese (Brazil / Portugal)
    "basketball": "basquete", "football": "futebol", "soccer": "futebol",
    "golf": "golfe", "tennis": "tênis", "swimming": "natação",
    "volleyball": "vôlei", "badminton": "badminton", "rugby": "rugby",
    "camp": "acampamento", "summer camp": "acampamento de verão",
    "academy": "academia", "school": "escola", "training": "treinamento",
    "club": "clube", "travel agency": "agência de viagens", "tour": "tour",
    "youth": "jovens", "junior": "juvenil", "coaching": "treinamento",
    "facility": "instalação", "program": "programa",
}

SPORT_IT = {  # Italian
    "basketball": "pallacanestro", "football": "calcio", "soccer": "calcio",
    "golf": "golf", "tennis": "tennis", "swimming": "nuoto",
    "volleyball": "pallavolo", "badminton": "badminton", "rugby": "rugby",
    "camp": "camp", "summer camp": "camp estivo", "academy": "accademia",
    "school": "scuola", "training": "allenamento", "club": "club",
    "travel agency": "agenzia di viaggi", "tour": "tour",
    "youth": "giovani", "junior": "junior", "coaching": "coaching",
    "facility": "struttura", "program": "programma",
}

SPORT_RU = {  # Russian
    "basketball": "баскетбол", "football": "футбол", "soccer": "футбол",
    "golf": "гольф", "tennis": "теннис", "swimming": "плавание",
    "volleyball": "волейбол", "badminton": "бадминтон", "rugby": "регби",
    "camp": "лагерь", "summer camp": "летний лагерь",
    "academy": "академия", "school": "школа", "training": "тренировка",
    "club": "клуб", "travel agency": "туристическое агентство",
    "tour": "тур", "youth": "молодёжь", "junior": "юниор",
    "coaching": "тренерство", "program": "программа",
}

SPORT_AR = {  # Arabic
    "basketball": "كرة السلة", "football": "كرة القدم",
    "golf": "الغولف", "tennis": "التنس", "swimming": "السباحة",
    "volleyball": "الكرة الطائرة",
    "camp": "مخيم", "summer camp": "مخيم صيفي",
    "academy": "أكاديمية", "school": "مدرسة", "training": "تدريب",
    "club": "نادي", "travel agency": "وكالة سفر", "tour": "جولة",
    "youth": "شباب", "junior": "ناشئ", "coaching": "تدريب",
}

SPORT_TH = {  # Thai
    "basketball": "บาสเกตบอล", "football": "ฟุตบอล",
    "golf": "กอล์ฟ", "tennis": "เทนนิส", "swimming": "ว่ายน้ำ",
    "camp": "แคมป์", "summer camp": "ค่ายฤดูร้อน",
    "academy": "อคาเดมี่", "school": "โรงเรียน", "training": "ฝึกซ้อม",
    "club": "สโมสร", "travel agency": "บริษัทท่องเที่ยว",
    "youth": "เยาวชน", "junior": "จูเนียร์",
}

SPORT_MS = {  # Malay / Indonesian (close enough to share)
    "basketball": "bola keranjang", "football": "bola sepak",
    "soccer": "bola sepak", "golf": "golf", "tennis": "tenis",
    "swimming": "renang", "volleyball": "bola voli",
    "camp": "kem", "summer camp": "kem sukan",
    "academy": "akademi", "school": "sekolah", "training": "latihan",
    "club": "kelab", "travel agency": "agen perjalanan",
    "youth": "belia", "junior": "junior",
}

SPORT_VI = {  # Vietnamese
    "basketball": "bóng rổ", "football": "bóng đá", "soccer": "bóng đá",
    "golf": "golf", "tennis": "quần vợt", "swimming": "bơi lội",
    "camp": "trại", "summer camp": "trại hè",
    "academy": "học viện", "school": "trường", "training": "đào tạo",
    "club": "câu lạc bộ", "travel agency": "công ty du lịch",
    "youth": "thanh niên", "junior": "thiếu niên",
}


# ── Language metadata ────────────────────────────────────────────────────────

LANGUAGES: dict[str, dict] = {
    "zh": {
        "name": "Chinese (Simplified)",
        "native": "中文（简体）",
        "sport": SPORT_ZH,
        "general": GENERAL_ZH,
        "region": REGION_ZH,
        "regions": ["sea", "china"],
    },
    "zh_tw": {
        "name": "Chinese (Traditional)",
        "native": "中文（繁體）",
        "sport": SPORT_ZH_TW,
        "general": {},
        "region": {},
        "regions": ["china"],
    },
    "ja": {
        "name": "Japanese",
        "native": "日本語",
        "sport": SPORT_JA,
        "general": {},
        "region": {},
        "regions": ["japan"],
    },
    "ko": {
        "name": "Korean",
        "native": "한국어",
        "sport": SPORT_KO,
        "general": {},
        "region": {},
        "regions": ["korea"],
    },
    "de": {
        "name": "German",
        "native": "Deutsch",
        "sport": SPORT_DE,
        "general": {},
        "region": {},
        "regions": ["europe"],
        "countries": ["germany", "austria", "switzerland"],
    },
    "nl": {
        "name": "Dutch",
        "native": "Nederlands",
        "sport": SPORT_NL,
        "general": {},
        "region": {},
        "regions": ["europe"],
        "countries": ["netherlands", "belgium"],
    },
    "fr": {
        "name": "French",
        "native": "Français",
        "sport": SPORT_FR,
        "general": {},
        "region": {},
        "regions": ["europe"],
        "countries": ["france", "belgium", "switzerland"],
    },
    "es": {
        "name": "Spanish",
        "native": "Español",
        "sport": SPORT_ES,
        "general": {},
        "region": {},
        "regions": ["europe", "latam"],
        "countries": ["spain", "mexico", "argentina", "colombia", "chile"],
    },
    "pt": {
        "name": "Portuguese",
        "native": "Português",
        "sport": SPORT_PT,
        "general": {},
        "region": {},
        "regions": ["europe", "latam"],
        "countries": ["brazil", "portugal"],
    },
    "it": {
        "name": "Italian",
        "native": "Italiano",
        "sport": SPORT_IT,
        "general": {},
        "region": {},
        "regions": ["europe"],
        "countries": ["italy"],
    },
    "ru": {
        "name": "Russian",
        "native": "Русский",
        "sport": SPORT_RU,
        "general": {},
        "region": {},
        "regions": ["europe"],
        "countries": ["russia", "ukraine", "belarus", "kazakhstan"],
    },
    "ar": {
        "name": "Arabic",
        "native": "العربية",
        "sport": SPORT_AR,
        "general": {},
        "region": {},
        "regions": ["middle_east"],
        "countries": ["dubai", "uae", "saudi", "qatar", "egypt"],
    },
    "th": {
        "name": "Thai",
        "native": "ภาษาไทย",
        "sport": SPORT_TH,
        "general": {},
        "region": {},
        "regions": ["sea"],
        "countries": ["thailand", "bangkok"],
    },
    "ms": {
        "name": "Malay / Indonesian",
        "native": "Bahasa Melayu / Indonesia",
        "sport": SPORT_MS,
        "general": {},
        "region": {},
        "regions": ["sea"],
        "countries": ["malaysia", "indonesia", "singapore"],
    },
    "vi": {
        "name": "Vietnamese",
        "native": "Tiếng Việt",
        "sport": SPORT_VI,
        "general": {},
        "region": {},
        "regions": ["sea"],
        "countries": ["vietnam", "hanoi", "ho chi minh"],
    },
}

# Which languages auto-activate for each macro-region
REGION_AUTO_LANGS: dict[str, list[str]] = {
    "sea":          ["zh", "th", "ms", "vi"],
    "china":        ["zh", "zh_tw"],
    "japan":        ["ja"],
    "korea":        ["ko"],
    "europe":       ["de", "nl", "fr", "es", "it"],
    "north_america": [],
    "latam":        ["es", "pt"],
    "middle_east":  ["ar"],
    "oceania":      [],
    "south_asia":   [],
    "africa":       [],
}
