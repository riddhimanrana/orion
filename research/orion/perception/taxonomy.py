"""Coarse → fine prompt taxonomy for YOLO-World crop refinement.

These mappings are intentionally high-recall on the coarse side and
fine-grained (including open-vocab long tail) on the refinement side.
"""

COARSE_TO_FINE_PROMPTS = {
    # Containers / drinkware
    "bottle": [
        "water bottle",
        "blue water bottle",
        "plastic bottle",
        "metal bottle",
        "thermos",
    ],
    "cup": [
        "coffee mug",
        "ceramic mug",
        "paper cup",
        "tea cup",
    ],
    "bowl": [
        "ceramic bowl",
        "plastic bowl",
        "metal bowl",
    ],

    # Personal electronics
    "cell phone": [
        "smartphone",
        "iphone",
        "android phone",
        "phone with case",
        "airpods case",
        "earbuds case",
    ],
    "laptop": [
        "laptop computer",
        "macbook",
        "gaming laptop",
    ],
    "keyboard": [
        "mechanical keyboard",
        "wireless keyboard",
        "laptop keyboard",
    ],
    "mouse": [
        "computer mouse",
        "wireless mouse",
        "gaming mouse",
    ],
    "remote": [
        "tv remote",
        "air conditioner remote",
        "media remote",
    ],
    "tv": [
        "television",
        "monitor",
        "screen",
    ],
    "monitor": [
        "computer monitor",
        "desktop monitor",
        "display screen",
    ],

    # Bags & carry items
    "backpack": [
        "backpack",
        "bag",
        "rucksack",
        "school bag",
    ],
    "handbag": [
        "purse",
        "tote bag",
        "shoulder bag",
    ],
    "suitcase": [
        "luggage",
        "rolling suitcase",
        "carry on suitcase",
    ],

    # Misc small objects
    "book": [
        "paperback book",
        "notebook",
        "textbook",
        "journal",
    ],
    "box": [
        "cardboard box",
        "shipping box",
        "shoe box",
    ],
    "umbrella": [
        "folding umbrella",
        "black umbrella",
    ],
}
