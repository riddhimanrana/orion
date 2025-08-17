
//
//  H264Encoder.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 8/14/25.
//  Handles H.264 video encoding using VideoToolbox.
//

import Foundation
import VideoToolbox
import CoreMedia

class H264Encoder {
    private var compressionSession: VTCompressionSession?
    private var width: Int32
    private var height: Int32

    var onEncodedFrame: ((CMSampleBuffer) -> Void)?

    init(width: Int, height: Int) {
        self.width = Int32(width)
        self.height = Int32(height)
        setupCompressionSession()
    }

    private func setupCompressionSession() {
        let status = VTCompressionSessionCreate(
            allocator: kCFAllocatorDefault,
            width: width,
            height: height,
            codecType: kCMVideoCodecType_H264,
            encoderSpecification: nil,
            imageBufferAttributes: nil,
            compressedDataAllocator: nil,
            outputCallback: { (outputCallbackRefCon, sourceFrameRefCon, status, flags, sampleBuffer) in
                guard status == noErr, let sampleBuffer = sampleBuffer else { return }
                guard let refCon = outputCallbackRefCon else { return }
                let encoder = Unmanaged<H264Encoder>.fromOpaque(refCon).takeUnretainedValue()
                encoder.onEncodedFrame?(sampleBuffer)
            },
            refcon: Unmanaged.passUnretained(self).toOpaque(),
            compressionSessionOut: &compressionSession
        )

        if status != noErr {
            print("H264Encoder: Failed to create compression session")
            return
        }

        guard let session = compressionSession else { return }

        // Configure for low-latency, real-time encoding
        VTSessionSetProperty(session, key: kVTCompressionPropertyKey_RealTime, value: kCFBooleanTrue)
        VTSessionSetProperty(session, key: kVTCompressionPropertyKey_AllowFrameReordering, value: kCFBooleanFalse)
        VTSessionSetProperty(session, key: kVTCompressionPropertyKey_ProfileLevel, value: kVTProfileLevel_H264_Baseline_AutoLevel)
        VTSessionSetProperty(session, key: kVTCompressionPropertyKey_AverageBitRate, value: (width * height * 2) as CFNumber)
    }

    func encode(sampleBuffer: CMSampleBuffer) {
        guard let session = compressionSession, let imageBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

        let presentationTimeStamp = CMSampleBufferGetPresentationTimeStamp(sampleBuffer)
        let duration = CMSampleBufferGetDuration(sampleBuffer)

        // Force each frame to be a keyframe (IDR)
        let frameProperties = [
            kVTEncodeFrameOptionKey_ForceKeyFrame: kCFBooleanTrue
        ] as CFDictionary

        VTCompressionSessionEncodeFrame(session, imageBuffer: imageBuffer, presentationTimeStamp: presentationTimeStamp, duration: duration, frameProperties: frameProperties, sourceFrameRefcon: nil, infoFlagsOut: nil)
    }

    func invalidate() {
        if let session = compressionSession {
            VTCompressionSessionInvalidate(session)
            self.compressionSession = nil
        }
    }

    deinit {
        invalidate()
    }
}
