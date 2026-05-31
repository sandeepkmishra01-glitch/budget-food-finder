import re
from collections import Counter

FOOD_NOUNS = {
    "taco", "tacos", "burrito", "burritos", "bowl", "bowls", "rice",
    "noodles", "noodle", "pizza", "burger", "burgers", "sandwich",
    "sandwiches", "wings", "wing", "fries", "soup", "soups", "salad",
    "salads", "sushi", "roll", "rolls", "ramen", "pho", "curry",
    "curries", "dumpling", "dumplings", "gyoza", "birria", "carnitas",
    "carne asada", "al pastor", "quesadilla", "quesadillas", "enchilada",
    "enchiladas", "nachos", "tamale", "tamales", "torta", "tortas",
    "elote", "pozole", "chilaquiles", "mole", "pad thai", "lo mein",
    "chow mein", "fried rice", "bibimbap", "bulgogi", "kimchi",
    "shawarma", "falafel", "hummus", "gyro", "gyros", "kebab", "kebabs",
    "tikka", "naan", "biryani", "samosa", "samosas", "paneer",
    "tandoori", "masala", "vindaloo", "korma", "dosa", "chaat",
    "pasta", "lasagna", "ravioli", "gnocchi", "risotto", "bruschetta",
    "calzone", "focaccia", "penne", "spaghetti", "fettuccine",
    "carbonara", "alfredo", "marinara", "bolognese", "pesto",
    "steak", "ribs", "brisket", "pulled pork", "smoked", "bbq",
    "chicken", "shrimp", "salmon", "fish", "crab", "lobster", "tuna",
    "poke", "ceviche", "calamari", "oysters", "clam", "clams",
    "wonton", "bao", "banh mi", "spring roll", "spring rolls",
    "egg roll", "egg rolls", "tempura", "teriyaki", "katsu",
    "udon", "soba", "miso", "edamame", "yakitori",
    "waffle", "waffles", "pancake", "pancakes", "crepe", "crepes",
    "croissant", "donut", "donuts", "bagel", "bagels", "muffin",
    "pie", "cake", "cookie", "cookies", "brownie", "brownies",
    "ice cream", "gelato", "smoothie", "acai", "matcha",
    "coffee", "latte", "espresso", "cappuccino", "mocha",
    "boba", "bubble tea", "chai", "kombucha",
    "hot dog", "corn dog", "pretzel", "popcorn",
    "mac and cheese", "grilled cheese", "philly cheesesteak",
    "club sandwich", "blt", "wrap", "wraps", "sub", "hoagie",
}

FOOD_ADJECTIVES = {
    "spicy", "crispy", "grilled", "fried", "smoked", "roasted",
    "bbq", "buffalo", "teriyaki", "garlic", "honey", "lemon",
    "sesame", "truffle", "loaded", "stuffed", "double", "classic",
    "signature", "house", "homemade", "fresh", "glazed", "braised",
    "seared", "blackened", "cajun", "creamy", "cheesy", "hot",
    "mild", "sweet", "sour", "tangy", "savory", "zesty",
}

_adj_pattern = "|".join(re.escape(a) for a in sorted(FOOD_ADJECTIVES, key=len, reverse=True))
_noun_pattern = "|".join(re.escape(n) for n in sorted(FOOD_NOUNS, key=len, reverse=True))

DISH_PATTERN = re.compile(
    rf"\b(?:(?:{_adj_pattern})\s+)?(?:{_noun_pattern})(?:\s+(?:{_noun_pattern}))?",
    re.IGNORECASE,
)


def extract_dishes(reviews: list[str], min_mentions: int = 2) -> list[str]:
    if not reviews:
        return []

    candidates = Counter()

    for review in reviews:
        matches = DISH_PATTERN.findall(review.lower()) if review else []
        found_in_review = set()
        for match in DISH_PATTERN.finditer(review.lower()):
            dish = match.group().strip()
            dish = _normalize_dish(dish)
            if dish and len(dish) > 2:
                found_in_review.add(dish)
        candidates.update(found_in_review)

    frequent = {
        dish: count
        for dish, count in candidates.items()
        if count >= min_mentions
    }

    sorted_dishes = sorted(frequent.items(), key=lambda x: x[1], reverse=True)
    return [dish for dish, _ in sorted_dishes[:5]]


def _normalize_dish(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"\s+", " ", name)
    return name


def extract_dishes_for_restaurants(restaurants: list[dict]) -> list[dict]:
    for restaurant in restaurants:
        raw_reviews = restaurant.pop("raw_reviews", [])
        if raw_reviews:
            restaurant["dish_mentions"] = extract_dishes(raw_reviews)
        elif "dish_mentions" not in restaurant:
            restaurant["dish_mentions"] = []
    return restaurants
