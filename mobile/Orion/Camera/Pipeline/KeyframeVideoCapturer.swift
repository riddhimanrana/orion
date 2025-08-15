
//
//  KeyframeVideoCapturer.swift
//  Orion
//
//  Created by Riddhiman Rana on 8/14/25.
//  A custom RTCVideoCapturer to feed encoded keyframes into the WebRTC pipeline.
//

import Foundation
import WebRTC

class KeyframeVideoCapturer: RTCVideoCapturer {
    
    func sendEncodedFrame(_ sampleBuffer: CMSampleBuffer) {
        guard let delegate = self.delegate else {
            print("KeyframeVideoCapturer: Delegate is nil.")
            return
        }
        
        // This is a simplified approach. A more robust solution might involve
        // converting the CMSampleBuffer to an RTCEncodedImage.
        // For now, we will assume the capturer can handle the buffer directly
        // if the track source is configured correctly.
        
        // The delegate method expects a CVPixelBuffer, so we extract it.
        // Note: This sends the *raw* frame. A true keyframe-as-video pipeline
        // would require a custom RTCVideoSource that accepts encoded frames.
        // This implementation will be updated once the WebRTC track is configured
        // to accept an encoded stream.
        if let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) {
            let timeStamp = CMSampleBufferGetPresentationTimeStamp(sampleBuffer)
            let timeStampNs = Int64(CMTimeGetSeconds(timeStamp) * 1_000_000_000)
            
            let rtcPixelBuffer = RTCCVPixelBuffer(pixelBuffer: pixelBuffer)
            let rtcVideoFrame = RTCVideoFrame(buffer: rtcPixelBuffer, rotation: ._0, timeStampNs: timeStampNs)
            delegate.capturer(self, didCapture: rtcVideoFrame)
        }
    }
}
