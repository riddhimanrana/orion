
import Foundation
import CoreImage
import MLX
import MLXLMCommon
import MLXVLM
import FastVLM
import Combine
import Tokenizers

@MainActor
@Observable
class FastVLMModel {

    // VLMResult is now nested inside the model, as requested.
    struct VLMResult: Hashable, Codable {
        let description: String
        let timeToFirstToken: TimeInterval
        let totalGenerationTime: TimeInterval
        let tokensGenerated: Int

        var tokensPerSecond: Double {
            guard totalGenerationTime > 0 else { return 0 }
            return Double(tokensGenerated) / totalGenerationTime
        }
    }

    // Public properties to drive UI, similar to the example app
    public var running = false
    public var modelInfo = ""
    public var output = ""
    public var promptTime: String = ""
    public var evaluationState = EvaluationState.idle

    // Internal state management using ModelContainer, as in the example
    private enum LoadState {
        case idle
        case loaded(ModelContainer)
    }
    private var loadState = LoadState.idle
    private var currentTask: Task<Void, Never>?
    
    enum EvaluationState: String, CaseIterable {
        case idle = "Idle"
        case processingPrompt = "Processing Prompt"
        case generatingResponse = "Generating Response"
    }

    private let modelConfiguration = FastVLM.modelConfiguration
    private let generateParameters = GenerateParameters(temperature: 0.7)
    private let maxTokens = 256
    private let displayEveryNTokens = 4

    init() {
        // The model registers itself with the factory, as in the example.
        FastVLM.register(modelFactory: VLMModelFactory.shared)
    }

    // Correctly loads the model using a ModelContainer
    private func _load() async throws -> ModelContainer {
        switch loadState {
        case .idle:
            MLX.GPU.set(cacheLimit: 20 * 1024 * 1024)
            let modelContainer = try await VLMModelFactory.shared.loadContainer(configuration: modelConfiguration)
            self.modelInfo = "Loaded"
            loadState = .loaded(modelContainer)
            return modelContainer
        case .loaded(let modelContainer):
            return modelContainer
        }
    }

    public func load() async {
        do {
            _ = try await _load()
            logInfo("FastVLM model loaded successfully.", category: .vision)
        } catch {
            self.modelInfo = "Error loading model: \(error)"
            logError(error, category: .vision)
        }
    }

    // This is the new generate function that integrates with CameraManager
    public func generate(prompt: String, image: CVPixelBuffer) async -> VLMResult {
        guard !running else {
            return VLMResult(description: "VLM Busy", timeToFirstToken: 0, totalGenerationTime: 0, tokensGenerated: 0)
        }
        
        running = true
        defer { running = false }

        do {
            let modelContainer = try await _load()
            let userInput = UserInput(prompt: .text(prompt), images: [.ciImage(CIImage(cvPixelBuffer: image))])
            
            let llmStart = Date()
            var promptDuration: TimeInterval = 0
            var generationStartTime: Date?
            var finalOutput = ""
            var finalTokenCount = 0

            let result = try await modelContainer.perform { context in
                Task { @MainActor in
                    self.evaluationState = .processingPrompt
                }
                let input = try await context.processor.prepare(input: userInput)
                var seenFirstToken = false

                let generateResult = try MLXLMCommon.generate(input: input, parameters: generateParameters, context: context) { tokens in
                    if !seenFirstToken {
                        seenFirstToken = true
                        generationStartTime = Date()
                        promptDuration = generationStartTime!.timeIntervalSince(llmStart)
                    }
                    if tokens.count % displayEveryNTokens == 0 {
                        let text = context.tokenizer.decode(tokens: tokens)
                        Task { @MainActor in self.output = text }
                    }
                    if tokens.count >= maxTokens { return .stop }
                    return .more
                }
                return generateResult
            }
            
            finalOutput = result.output
            finalTokenCount = result.tokens.count
            
            let totalTime = Date().timeIntervalSince(llmStart)
            
            return VLMResult(
                description: finalOutput,
                timeToFirstToken: promptDuration,
                totalGenerationTime: totalTime,
                tokensGenerated: finalTokenCount
            )

        } catch {
            logError(error, category: .vision)
            return VLMResult(description: "Error: \(error.localizedDescription)", timeToFirstToken: 0, totalGenerationTime: 0, tokensGenerated: 0)
        }
    }
}
