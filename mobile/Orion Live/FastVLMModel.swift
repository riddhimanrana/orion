//
//  FastVLMModel.swift
//  Orion Live
//
//  Created by Riddhiman Rana on 7/22/25.
//

import Foundation
import CoreImage
import MLX
import MLXLMCommon
import MLXVLM
import FastVLM
import Combine
import Tokenizers

@MainActor
class FastVLMModel: ObservableObject {

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

    public var running = false
    @Published public var modelInfo = ""
    @Published public var output = ""
    @Published public var promptTime: String = ""
    @Published public var evaluationState = EvaluationState.idle

    private enum LoadState { case idle, loaded(ModelContainer) }
    private var loadState = LoadState.idle

    enum EvaluationState: String, CaseIterable { case idle = "Idle", processingPrompt = "Processing Prompt", generatingResponse = "Generating Response" }

    private let modelConfiguration = FastVLM.modelConfiguration
    private let generateParameters = GenerateParameters(temperature: 0.7)
    private let maxTokens = 256
    private let displayEveryNTokens = 4

    // Actor to safely manage state across concurrent tasks
    private actor GenerationState {
        var promptDuration: TimeInterval = 0
        var generationStartTime: Date?
        var seenFirstToken = false

        func markFirstToken(llmStartTime: Date) {
            guard !seenFirstToken else { return }
            seenFirstToken = true
            let now = Date()
            self.generationStartTime = now
            self.promptDuration = now.timeIntervalSince(llmStartTime)
        }
    }

    init() {
        FastVLM.register(modelFactory: VLMModelFactory.shared)
    }

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
            let state = GenerationState()

            let result = try await modelContainer.perform { context in
                Task { @MainActor in self.evaluationState = .processingPrompt }
                let input = try await context.processor.prepare(input: userInput)

                let generateResult = try MLXLMCommon.generate(input: input, parameters: generateParameters, context: context) { tokens in
                    Task {
                        await state.markFirstToken(llmStartTime: llmStart)
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

            let finalOutput = result.output
            let finalTokenCount = result.tokens.count
            let totalTime = Date().timeIntervalSince(llmStart)
            let finalPromptDuration = await state.promptDuration

            return VLMResult(
                description: finalOutput,
                timeToFirstToken: finalPromptDuration,
                totalGenerationTime: totalTime,
                tokensGenerated: finalTokenCount
            )

        } catch {
            logError(error, category: .vision)
            return VLMResult(description: "Error: \(error.localizedDescription)", timeToFirstToken: 0, totalGenerationTime: 0, tokensGenerated: 0)
        }
    }
}
