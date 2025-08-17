//
//  CameraView.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 6/11/25.
//  Updated to fix EnvironmentObject and binding errors
//

import SwiftUI
import AVFoundation

/// Wraps UIKit preview + overlays for use in SwiftUI
struct CameraView: UIViewRepresentable {
    @EnvironmentObject var cameraManager: CameraManager

    func makeUIView(context: Context) -> CameraPreviewView {
        let previewView = CameraPreviewView()
        // grab and install the AVCaptureVideoPreviewLayer
        previewView.previewLayer = cameraManager.getPreviewLayer()
        return previewView
    }

    func updateUIView(_ uiView: CameraPreviewView, context: Context) {
        // push the latest detections into the overlay view
        uiView.updateDetections(cameraManager.lastDetections)
    }
}

/// A UIView that hosts the camera preview layer and draws detection boxes
class CameraPreviewView: UIView {
    // whenever this is set, install the layer as a sublayer
    var previewLayer: AVCaptureVideoPreviewLayer? {
        didSet {
            guard let layer = previewLayer else { return }
            self.layer.addSublayer(layer)
            layer.frame = bounds
        }
    }

    private var detectionOverlays: [DetectionOverlayView] = []

    override func layoutSubviews() {
        super.layoutSubviews()
        previewLayer?.frame = bounds
        // if the view resizes (e.g. rotation), refresh boxes
        updateOverlayFrames()
    }

    /// Called by SwiftUI whenever `lastDetections` changes
    func updateDetections(_ detections: [NetworkDetection]) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.clearOverlays()
            self.addDetectionOverlays(detections)
        }
    }

    private func clearOverlays() {
        detectionOverlays.forEach { $0.removeFromSuperview() }
        detectionOverlays.removeAll()
    }

    private func addDetectionOverlays(_ detections: [NetworkDetection]) {
        guard SettingsManager.shared.showDetectionBoxes else { return }
        for det in detections {
            let overlay = DetectionOverlayView(detection: det)
            addSubview(overlay)
            detectionOverlays.append(overlay)
            overlay.frame = convertNormalizedRect(det.bbox)
        }
    }

    private func convertNormalizedRect(_ norm: [Float]) -> CGRect {
        guard norm.count == 4 else { return .zero }
        let minX = CGFloat(norm[0]) * bounds.width
        let minY = CGFloat(norm[1]) * bounds.height
        let maxX = CGFloat(norm[2]) * bounds.width
        let maxY = CGFloat(norm[3]) * bounds.height
        return CGRect(x: minX,
                      y: minY,
                      width: maxX - minX,
                      height: maxY - minY)
    }

    private func updateOverlayFrames() {
        for overlay in detectionOverlays {
            if let det = overlay.detection {
                overlay.frame = convertNormalizedRect(det.bbox)
            }
        }
    }
}

/// A UIView subclass that draws a single detection box + label
class DetectionOverlayView: UIView {
    let detection: NetworkDetection?
    private let label = UILabel()

    init(detection: NetworkDetection) {
        self.detection = detection
        super.init(frame: .zero)
        setupView()
    }

    required init?(coder: NSCoder) {
        self.detection = nil
        super.init(coder: coder)
        setupView()
    }

    private func setupView() {
        backgroundColor = .clear
        layer.borderWidth = 2
        layer.borderColor = UIColor.systemBlue.cgColor
        layer.cornerRadius = 4

        // Label styling
        label.backgroundColor = UIColor.systemBlue.withAlphaComponent(0.8)
        label.textColor = .white
        label.font = .systemFont(ofSize: 12, weight: .medium)
        label.textAlignment = .center
        label.layer.cornerRadius = 4
        label.clipsToBounds = true
        if SettingsManager.shared.showDetectionLabels {
            if let det = detection {
                label.text = "\(det.label) (\(Int(det.confidence * 100))%)"
            }
        } else {
            label.isHidden = true
        }

        addSubview(label)
        label.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            label.bottomAnchor.constraint(equalTo: topAnchor, constant: -4),
            label.leadingAnchor.constraint(equalTo: leadingAnchor),
            label.heightAnchor.constraint(equalToConstant: 20),
            label.widthAnchor.constraint(greaterThanOrEqualToConstant: 60)
        ])
    }

    override func draw(_ rect: CGRect) {
        super.draw(rect)
        guard let ctx = UIGraphicsGetCurrentContext() else { return }

        // draw the box
        ctx.setStrokeColor(UIColor.systemBlue.cgColor)
        ctx.setLineWidth(2)
        ctx.stroke(rect)

        // corner indicators
        let length: CGFloat = 10
        ctx.setStrokeColor(UIColor.systemYellow.cgColor)
        ctx.setLineWidth(3)

        // top-left
        ctx.move(to: CGPoint(x: 0, y: length))
        ctx.addLine(to: .zero)
        ctx.addLine(to: CGPoint(x: length, y: 0))

        // top-right
        ctx.move(to: CGPoint(x: rect.width - length, y: 0))
        ctx.addLine(to: CGPoint(x: rect.width, y: 0))
        ctx.addLine(to: CGPoint(x: rect.width, y: length))

        // bottom-left
        ctx.move(to: CGPoint(x: 0, y: rect.height - length))
        ctx.addLine(to: CGPoint(x: 0, y: rect.height))
        ctx.addLine(to: CGPoint(x: length, y: rect.height))

        // bottom-right
        ctx.move(to: CGPoint(x: rect.width - length, y: rect.height))
        ctx.addLine(to: CGPoint(x: rect.width, y: rect.height))
        ctx.addLine(to: CGPoint(x: rect.width, y: rect.height - length))

        ctx.strokePath()
    }
}

#if DEBUG
struct CameraView_Previews: PreviewProvider {
    static var previews: some View {
        CameraView()
            .environmentObject(CameraManager())
    }
}
#endif
