// Encode captured native frames at their measured wall-clock timestamps.
// Usage: swiftc ... -o /tmp/ae2-encode; /tmp/ae2-encode /absolute/plan.json
import Foundation
import AVFoundation
import CoreVideo
import ImageIO

struct Frame: Decodable {let file:String;let seconds:Double}
struct Plan: Decodable {let output:String;let width:Int;let height:Int;let duration:Double;let frames:[Frame];let verification_dir:String?}
enum EncodingError: Error {case failed(String)}

func encode(_ plan:Plan) throws {
    guard !plan.frames.isEmpty else {throw EncodingError.failed("No source frames")}
    let url=URL(fileURLWithPath:plan.output)
    if FileManager.default.fileExists(atPath:url.path) {try FileManager.default.removeItem(at:url)}
    let writer=try AVAssetWriter(outputURL:url,fileType:.mp4)
    writer.movieTimeScale=60000
    let settings:[String:Any]=[
        AVVideoCodecKey:AVVideoCodecType.h264,AVVideoWidthKey:plan.width,AVVideoHeightKey:plan.height,
        AVVideoCompressionPropertiesKey:[AVVideoAverageBitRateKey:2_400_000,AVVideoMaxKeyFrameIntervalKey:24,
                                        AVVideoProfileLevelKey:AVVideoProfileLevelH264HighAutoLevel],
        AVVideoColorPropertiesKey:[AVVideoColorPrimariesKey:AVVideoColorPrimaries_ITU_R_709_2,
                                  AVVideoTransferFunctionKey:AVVideoTransferFunction_ITU_R_709_2,
                                  AVVideoYCbCrMatrixKey:AVVideoYCbCrMatrix_ITU_R_709_2]]
    let input=AVAssetWriterInput(mediaType:.video,outputSettings:settings)
    input.expectsMediaDataInRealTime=false
    input.mediaTimeScale=60000
    let attributes:[String:Any]=[kCVPixelBufferPixelFormatTypeKey as String:kCVPixelFormatType_32BGRA,
        kCVPixelBufferWidthKey as String:plan.width,kCVPixelBufferHeightKey as String:plan.height,
        kCVPixelBufferCGImageCompatibilityKey as String:true,kCVPixelBufferCGBitmapContextCompatibilityKey as String:true]
    let adaptor=AVAssetWriterInputPixelBufferAdaptor(assetWriterInput:input,sourcePixelBufferAttributes:attributes)
    writer.add(input)
    guard writer.startWriting() else {throw EncodingError.failed(String(describing:writer.error))}
    writer.startSession(atSourceTime:.zero)
    for frame in plan.frames {
        let deadline=Date().addingTimeInterval(30)
        while !input.isReadyForMoreMediaData {
            guard writer.status == .writing && Date()<deadline else {throw EncodingError.failed(String(describing:writer.error))}
            Thread.sleep(forTimeInterval:0.003)
        }
        try autoreleasepool {
            guard let source=CGImageSourceCreateWithURL(URL(fileURLWithPath:frame.file) as CFURL,nil),
                  let image=CGImageSourceCreateImageAtIndex(source,0,nil),let pool=adaptor.pixelBufferPool else {
                throw EncodingError.failed("Cannot decode source frame: "+frame.file)
            }
            var optional:CVPixelBuffer?
            guard CVPixelBufferPoolCreatePixelBuffer(nil,pool,&optional)==kCVReturnSuccess,let buffer=optional else {
                throw EncodingError.failed("Pixel-buffer allocation failed")
            }
            CVPixelBufferLockBaseAddress(buffer,[])
            defer {CVPixelBufferUnlockBaseAddress(buffer,[])}
            let flags=CGBitmapInfo.byteOrder32Little.rawValue|CGImageAlphaInfo.premultipliedFirst.rawValue
            guard let context=CGContext(data:CVPixelBufferGetBaseAddress(buffer),width:plan.width,height:plan.height,
                    bitsPerComponent:8,bytesPerRow:CVPixelBufferGetBytesPerRow(buffer),
                    space:CGColorSpace(name:CGColorSpace.sRGB)!,bitmapInfo:flags) else {throw EncodingError.failed("Cannot draw frame")}
            context.draw(image,in:CGRect(x:0,y:0,width:plan.width,height:plan.height))
            guard adaptor.append(buffer,withPresentationTime:CMTime(seconds:frame.seconds,preferredTimescale:60000)) else {
                throw EncodingError.failed(String(describing:writer.error))
            }
        }
    }
    writer.endSession(atSourceTime:CMTime(seconds:plan.duration,preferredTimescale:60000))
    input.markAsFinished()
    let done=DispatchSemaphore(value:0)
    writer.finishWriting {done.signal()}
    guard done.wait(timeout:.now()+60) == .success,writer.status == .completed else {throw EncodingError.failed(String(describing:writer.error))}
    if let directory=plan.verification_dir {
        try FileManager.default.createDirectory(atPath:directory,withIntermediateDirectories:true)
        let asset=AVURLAsset(url:url)
        guard let track=asset.tracks(withMediaType:.video).first,
              let format=track.formatDescriptions.first else {throw EncodingError.failed("Missing video track")}
        let subtype=CMFormatDescriptionGetMediaSubType(format as! CMFormatDescription)
        let codec=String(bytes:[UInt8((subtype>>24)&255),UInt8((subtype>>16)&255),UInt8((subtype>>8)&255),UInt8(subtype&255)],encoding:.ascii) ?? "unknown"
        guard codec=="avc1" else {throw EncodingError.failed("Expected H.264")}
        let generator=AVAssetImageGenerator(asset:asset);generator.appliesPreferredTrackTransform=true
        for (name,seconds) in [("first",0.0),("last",(plan.frames.last!.seconds+plan.duration)/2)] {
            generator.requestedTimeToleranceBefore = .zero;generator.requestedTimeToleranceAfter = .zero
            let image=try generator.copyCGImage(at:CMTime(seconds:seconds,preferredTimescale:60000),actualTime:nil)
            let target=URL(fileURLWithPath:directory).appendingPathComponent(name+".png")
            guard let destination=CGImageDestinationCreateWithURL(target as CFURL,"public.png" as CFString,1,nil) else {throw EncodingError.failed("Cannot save verification frame")}
            CGImageDestinationAddImage(destination,image,nil)
            guard CGImageDestinationFinalize(destination) else {throw EncodingError.failed("Verification frame failed")}
        }
        let record:[String:Any]=["codec":codec,"width":Int(track.naturalSize.width),"height":Int(track.naturalSize.height),
                                 "duration_seconds":CMTimeGetSeconds(asset.duration),"source_frames":plan.frames.count]
        try JSONSerialization.data(withJSONObject:record,options:[.prettyPrinted,.sortedKeys]).write(to:URL(fileURLWithPath:directory).appendingPathComponent("inspection.json"))
    }
    print("Encoded H.264:",plan.frames.count,"actual frames;",plan.duration,"seconds")
}

do {
    let plan=try JSONDecoder().decode(Plan.self,from:Data(contentsOf:URL(fileURLWithPath:CommandLine.arguments[1])))
    try encode(plan)
} catch {fputs("Documentation encoding failed: \(error)\n",stderr);exit(1)}
