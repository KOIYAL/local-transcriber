// apple-intelligence-helper — a thin JSON bridge to the on-device Apple
// Intelligence foundation model, for the Python backend (which cannot call
// the Swift-only FoundationModels framework directly).
//
//   apple-intelligence-helper check
//     -> {"available": true, "context_size": 4096}
//     -> {"available": false, "reason": "..."}
//
//   echo '{"instructions": "...", "text": "..."}' | apple-intelligence-helper summarize
//     -> {"summary": "..."}
//     -> {"error": "context_overflow"}   (exit 1; caller splits and retries)
//
// Build (macOS 26+ SDK required; see README.md next to this file):
//   swiftc -O -parse-as-library main.swift -o ../../vendor/apple-intelligence-helper
//
// NOTE: scaffold written off-platform; compile and smoke-test on a Mac
// before shipping.

import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

struct SummarizeRequest: Codable {
    let instructions: String
    let text: String
}

func emit(_ object: [String: Any], exitCode: Int32) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: object)
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write("\n".data(using: .utf8)!)
    exit(exitCode)
}

@main
enum Main {
    static func main() async {
        let command = CommandLine.arguments.dropFirst().first ?? ""
        switch command {
        case "check":
            await check()
        case "summarize":
            await summarize()
        default:
            emit(["error": "usage: apple-intelligence-helper <check|summarize>"], exitCode: 2)
        }
    }

    static func check() async {
        #if canImport(FoundationModels)
        guard #available(macOS 26.0, *) else {
            emit(["available": false, "reason": "macos_too_old"], exitCode: 0)
        }
        let model = SystemLanguageModel.default
        switch model.availability {
        case .available:
            var contextSize = 4096
            if #available(macOS 26.4, *) {
                contextSize = model.contextSize
            }
            emit(["available": true, "context_size": contextSize], exitCode: 0)
        case .unavailable(let reason):
            emit(["available": false, "reason": "\(reason)"], exitCode: 0)
        }
        #else
        emit(["available": false, "reason": "sdk_without_foundation_models"], exitCode: 0)
        #endif
    }

    static func summarize() async {
        #if canImport(FoundationModels)
        guard #available(macOS 26.0, *) else {
            emit(["error": "macos_too_old"], exitCode: 1)
        }
        let input = FileHandle.standardInput.readDataToEndOfFile()
        guard let request = try? JSONDecoder().decode(SummarizeRequest.self, from: input) else {
            emit(["error": "invalid_input"], exitCode: 2)
        }
        let session = LanguageModelSession(instructions: request.instructions)
        do {
            let response = try await session.respond(to: request.text)
            emit(["summary": response.content], exitCode: 0)
        } catch let error as LanguageModelSession.GenerationError {
            if case .exceededContextWindowSize = error {
                emit(["error": "context_overflow"], exitCode: 1)
            }
            emit(["error": "\(error)"], exitCode: 1)
        } catch {
            emit(["error": "\(error)"], exitCode: 1)
        }
        #else
        emit(["error": "sdk_without_foundation_models"], exitCode: 1)
        #endif
    }
}
