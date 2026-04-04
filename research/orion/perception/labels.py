"""
Label Normalization Module
==========================

Central location for label normalization logic used across:
- Re-ID matching (phase 2)
- Tracking (phase 1)  
- Memory object creation

Groups semantic duplicates for better clustering and memory coherence.
"""

from typing import Dict


# Canonical label normalization map - group semantic duplicates
LABEL_NORMALIZATION: Dict[str, str] = {
    # Screen/display devices
    "computer screen": "monitor",
    "computer monitor": "monitor",
    "television": "monitor",
    "tv": "monitor",
    "screen": "monitor",
    "display": "monitor",
    "computer": "monitor",
    "desktop": "monitor",
    "lcd": "monitor",
    
    # Seating
    "office chair": "chair",
    "armchair": "chair",
    "stool": "chair",
    "seat": "chair",
    "swivel chair": "chair",
    "gaming chair": "chair",
    "folding chair": "chair",
    
    # Bottles
    "water bottle": "bottle",
    "plastic bottle": "bottle",
    "glass bottle": "bottle",
    "beverage bottle": "bottle",
    
    # Couches/sofas
    "sofa": "couch",
    "loveseat": "couch",
    "settee": "couch",
    "sectional": "couch",
    
    # Plants
    "houseplant": "plant",
    "potted plant": "plant",
    "indoor plant": "plant",
    "flower pot": "plant",
    
    # Tables/surfaces
    "counter": "table",
    "countertop": "table",
    "desk": "table",
    "dining table": "table",
    "coffee table": "table",
    "side table": "table",
    "end table": "table",
    "nightstand": "table",
    "work surface": "table",
    
    # Lighting
    "floor lamp": "lamp",
    "table lamp": "lamp",
    "desk lamp": "lamp",
    "reading lamp": "lamp",
    "standing lamp": "lamp",
    
    # Wall art/pictures
    "artwork": "picture",
    "painting": "picture",
    "picture frame": "picture",
    "frame": "picture",
    "poster": "picture",
    "print": "picture",
    "wall art": "picture",
    "canvas": "picture",
    
    # Floor coverings
    "carpet": "rug",
    "mat": "rug",
    "floor mat": "rug",
    "area rug": "rug",
    "doormat": "rug",
    
    # Pillows/cushions
    "cushion": "pillow",
    "throw pillow": "pillow",
    "decorative pillow": "pillow",
    
    # Books/reading
    "textbook": "book",
    "notebook": "book",
    "magazine": "book",
    "manual": "book",
    
    # Cups/mugs
    "mug": "cup",
    "coffee cup": "cup",
    "tea cup": "cup",
    "tumbler": "cup",
    
    # Bags
    "backpack": "bag",
    "handbag": "bag",
    "purse": "bag",
    "tote": "bag",
    "messenger bag": "bag",
    
    # Keyboards
    "mechanical keyboard": "keyboard",
    "computer keyboard": "keyboard",
    "wireless keyboard": "keyboard",
    
    # Mice
    "computer mouse": "mouse",
    "wireless mouse": "mouse",
    "gaming mouse": "mouse",
    
    # Phones
    "cell phone": "phone",
    "mobile phone": "phone",
    "smartphone": "phone",
    "telephone": "phone",
    "cellphone": "phone",
    
    # Remotes
    "remote control": "remote",
    "tv remote": "remote",
    "controller": "remote",
    
    # Storage
    "cabinet": "storage",
    "shelf": "storage",
    "bookshelf": "storage",
    "drawer": "storage",
    "wardrobe": "storage",
    "closet": "storage",
    
    # Appliances
    "microwave oven": "microwave",
    "toaster oven": "toaster",
    "fridge": "refrigerator",
    
    # Clocks
    "wall clock": "clock",
    "alarm clock": "clock",
    "digital clock": "clock",
}


def normalize_label(label: str) -> str:
    """
    Normalize a label to its canonical form for better Re-ID clustering.
    
    Args:
        label: Raw label from detection/tracking
        
    Returns:
        Normalized canonical label (lowercase)
        
    Example:
        >>> normalize_label("Computer Monitor")
        'monitor'
        >>> normalize_label("coffee table")
        'table'
    """
    label_lower = label.lower().strip()
    return LABEL_NORMALIZATION.get(label_lower, label_lower)


def get_category_classes(category: str) -> list[str]:
    """
    Get all classes that normalize to a given category.
    
    Args:
        category: Canonical category name (e.g., 'monitor', 'chair')
        
    Returns:
        List of all class names that normalize to this category
        
    Example:
        >>> get_category_classes('monitor')
        ['computer screen', 'computer monitor', 'television', 'tv', 'screen', ...]
    """
    return [k for k, v in LABEL_NORMALIZATION.items() if v == category]


def is_furniture(label: str) -> bool:
    """Check if a label represents furniture (not portable)."""
    normalized = normalize_label(label)
    furniture = {"bed", "couch", "sofa", "table", "desk", "chair", "bench", 
                 "cabinet", "refrigerator", "storage", "wardrobe"}
    return normalized in furniture


def is_portable(label: str) -> bool:
    """Check if a label represents a portable object."""
    normalized = normalize_label(label)
    portable = {"book", "bottle", "cup", "phone", "laptop", "remote", 
                "keyboard", "mouse", "bag", "pillow"}
    return normalized in portable
