import Foundation

func getSpatialLabel(from bbox: [Float]) -> String {
    guard bbox.count == 4 else { return "center" }

    let xCenter = (bbox[0] + bbox[2]) / 2
    let yCenter = (bbox[1] + bbox[3]) / 2

    let vertical: String
    if yCenter < 0.33 { vertical = "top" }
    else if yCenter > 0.66 { vertical = "bottom" }
    else { vertical = "center" }

    let horizontal: String
    if xCenter < 0.33 { horizontal = "left" }
    else if xCenter > 0.66 { horizontal = "right" }
    else { horizontal = "center" }

    if vertical == "center" && horizontal == "center" { return "center" }
    if vertical == "center" { return horizontal }
    if horizontal == "center" { return vertical }

    return "\(vertical) \(horizontal)"
}
