from typing import List

def get_spatial_label(bbox: List[float]) -> str:
    """Converts bounding box to a spatial label."""
    x_center = (bbox[0] + bbox[2]) / 2
    y_center = (bbox[1] + bbox[3]) / 2

    if y_center < 0.33:
        vertical = "top"
    elif y_center > 0.66:
        vertical = "bottom"
    else:
        vertical = "center"

    if x_center < 0.33:
        horizontal = "left"
    elif x_center > 0.66:
        horizontal = "right"
    else:
        horizontal = "center"

    if vertical == "center" and horizontal == "center":
        return "center"
    if vertical == "center":
        return horizontal
    if horizontal == "center":
        return vertical

    return f"{vertical} {horizontal}"