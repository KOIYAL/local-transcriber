import AppKit
import Foundation

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let screenshotsDirectory = root.appendingPathComponent("store-assets/screenshots")
let logoURL = root.appendingPathComponent("assets/app-icon.png")

guard let logo = NSImage(contentsOf: logoURL) else {
    fatalError("Could not read \(logoURL.path)")
}

let fileManager = FileManager.default
let files = try fileManager.subpathsOfDirectory(atPath: screenshotsDirectory.path)
    .filter { $0.hasSuffix(".png") }
    .map { screenshotsDirectory.appendingPathComponent($0) }

for file in files {
    guard let source = NSImage(contentsOf: file) else {
        fatalError("Could not read \(file.path)")
    }

    let size = source.size
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: Int(size.width),
        pixelsHigh: Int(size.height),
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ) else {
        fatalError("Could not create bitmap for \(file.path)")
    }

    let context = NSGraphicsContext(bitmapImageRep: bitmap)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    context.imageInterpolation = .high
    source.draw(in: NSRect(origin: .zero, size: size))

    let containerWidth = min(CGFloat(1120), size.width - 40)
    let x = (size.width - containerWidth) / 2
    let y = size.height - 23 - 36
    logo.draw(in: NSRect(x: x, y: y, width: 36, height: 36))
    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        fatalError("Could not encode \(file.path)")
    }
    try png.write(to: file)
    print("Updated \(file.path)")
}
