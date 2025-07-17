//
// For licensing see accompanying LICENSE file.
// Copyright (C) 2025 Apple Inc. All Rights Reserved.
//

import Accelerate
import CoreImage
import MLX
import MLXLMCommon
import MLXVLM

/// Additions to MediaProcessing -- not currently present in mlx-libraries
enum MediaProcessingExtensions {

    // this function is not exported in current mlx-swift-examples -- local copy until it is exposed
    // properly
    public static func apply(_ image: CIImage, processing: UserInput.Processing?) -> CIImage {
        var image = image

        if let resize = processing?.resize {
            let scale = MediaProcessing.bestFitScale(image.extent.size, in: resize)
            image = image.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
        }

        return image
    }

    public static func rectSmallerOrEqual(_ extent: CGRect, size: CGSize) -> Bool {
        return extent.width <= size.width && extent.height <= size.height
    }

    public static func centerCrop(_ extent: CGRect, size: CGSize) -> CGRect {
        let targetWidth = min(extent.width, size.width)
        let targetHeight = min(extent.height, size.height)

        return CGRect(
            x: (extent.maxX - targetWidth) / 2,
            y: (extent.maxY - targetHeight) / 2,
            width: targetWidth, height: targetHeight
        )
    }

    public static func centerCrop(_ image: CIImage, size: CGSize) -> CIImage {
        let extent = image.extent
        if rectSmallerOrEqual(extent, size: size) {
            return image
        }

        let crop = centerCrop(extent, size: size)
        return
            image
            .cropped(to: crop)
            .transformed(by: CGAffineTransform(translationX: -crop.minX, y: -crop.minY))
    }

    public static func fitIn(_ size: CGSize, shortestEdge: Int) -> CGSize {
        let floatShortestEdge = CGFloat(shortestEdge)

        let (short, long) =
            size.width <= size.height ? (size.width, size.height) : (size.height, size.width)
        let newShort = floatShortestEdge
        let newLong = floatShortestEdge * long / short

        return size.width <= size.height
            ? CGSize(width: newShort, height: newLong) : CGSize(width: newLong, height: newShort)
    }

    public static func fitIn(_ size: CGSize, longestEdge: Int) -> CGSize {
        let floatLongestEdge = CGFloat(longestEdge)

        var (newShort, newLong) =
            size.width <= size.height ? (size.width, size.height) : (size.height, size.width)

        if newLong > floatLongestEdge {
            newLong = floatLongestEdge
            newShort = floatLongestEdge * newShort / newLong
        }

        return size.width <= size.height
            ? CGSize(width: newShort, height: newLong) : CGSize(width: newLong, height: newShort)
    }

    // version of function from https://github.com/ml-explore/mlx-swift-examples/pull/222
    public static func resampleBicubic(_ image: CIImage, to size: CGSize) -> CIImage {
        // Create a bicubic scale filter

        let yScale = size.height / image.extent.height
        let xScale = size.width / image.extent.width

        let filter = CIFilter.bicubicScaleTransform()
        filter.inputImage = image
        filter.scale = Float(yScale)
        filter.aspectRatio = Float(xScale / yScale)
        let scaledImage = filter.outputImage!

        // Create a rect with the exact dimensions we want
        let exactRect = CGRect(
            x: 0,
            y: 0,
            width: size.width,
            height: size.height
        )
        // Crop to ensure exact dimensions
        return scaledImage.cropped(to: exactRect)
    }

    static let context = CIContext()

    /// Convert the CIImage into a planar 3 channel MLXArray `[1, C, H, W]`.
    ///
    /// This physically moves the channels into a planar configuration -- this is
    /// required for feeding into the CoreML model and is faster to use
    /// dedicated functions than transforming into contiguous memory
    /// on readout.
    static public func asPlanarMLXArray(_ image: CIImage, colorSpace: CGColorSpace? = nil)
        -> MLXArray
    {
        let size = image.extent.size
        let w = Int(size.width.rounded())
        let h = Int(size.height.rounded())

        // probably not strictly necessary, but this is what happens in
        // e.g. image_processing_siglip in transformers (float32)
        let format = CIFormat.RGBAf
        let componentsPerPixel = 4
        let bytesPerComponent: Int = MemoryLayout<Float32>.size
        let bytesPerPixel = componentsPerPixel * bytesPerComponent
        let bytesPerRow = w * bytesPerPixel

        var data = Data(count: w * h * bytesPerPixel)
        var planarData = Data(count: 3 * w * h * bytesPerComponent)
        data.withUnsafeMutableBytes { ptr in
            context.render(
                image, toBitmap: ptr.baseAddress!, rowBytes: bytesPerRow, bounds: image.extent,
                format: format, colorSpace: colorSpace)
            context.clearCaches()

            let vh = vImagePixelCount(h)
            let vw = vImagePixelCount(w)

            // convert from RGBAf -> RGBf in place
            let rgbBytesPerRow = w * 3 * bytesPerComponent
            var rgbaSrc = vImage_Buffer(
                data: ptr.baseAddress!, height: vh, width: vw, rowBytes: bytesPerRow)
            var rgbDest = vImage_Buffer(
                data: ptr.baseAddress!, height: vh, width: vw, rowBytes: rgbBytesPerRow)

            vImageConvert_RGBAFFFFtoRGBFFF(&rgbaSrc, &rgbDest, vImage_Flags(kvImageNoFlags))

            // and convert to planar data in a second buffer
            planarData.withUnsafeMutableBytes { planarPtr in
                let planeBytesPerRow = w * bytesPerComponent

                var rDest = vImage_Buffer(
                    data: planarPtr.baseAddress!.advanced(by: 0 * planeBytesPerRow * h), height: vh,
                    width: vw, rowBytes: planeBytesPerRow)
                var gDest = vImage_Buffer(
                    data: planarPtr.baseAddress!.advanced(by: 1 * planeBytesPerRow * h), height: vh,
                    width: vw, rowBytes: planeBytesPerRow)
                var bDest = vImage_Buffer(
                    data: planarPtr.baseAddress!.advanced(by: 2 * planeBytesPerRow * h), height: vh,
                    width: vw, rowBytes: planeBytesPerRow)

                vImageConvert_RGBFFFtoPlanarF(
                    &rgbDest, &rDest, &gDest, &bDest, vImage_Flags(kvImageNoFlags))
            }
        }

        return MLXArray(planarData, [1, 3, h, w], type: Float32.self)
    }

}
