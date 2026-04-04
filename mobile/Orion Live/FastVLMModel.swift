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

    private enum LoadState { case idle, loading, loaded(ModelContainer), failed(Error) }
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
        // Only register the factory, don't load anything heavy
        FastVLM.register(modelFactory: VLMModelFactory.shared)
        self.modelInfo = "Ready to load"
    }

    private func _load() async throws -> ModelContainer {
        switch loadState {
        case .idle:
            loadState = .loading
            self.modelInfo = "Loading..."
            do {
                let t0 = CFAbsoluteTimeGetCurrent()
                MLX.GPU.set(cacheLimit: 20 * 1024 * 1024)
                let modelContainer = try await VLMModelFactory.shared.loadContainer(configuration: modelConfiguration)
                self.modelInfo = "Loaded"
                loadState = .loaded(modelContainer)
                let elapsed = (CFAbsoluteTimeGetCurrent() - t0)
                logInfo(String(format: "FastVLM load completed in %.2f s", elapsed), category: .vision)
                return modelContainer
            } catch {
                loadState = .failed(error)
                throw error
            }
        case .loading:
            // If already loading, wait for it to complete
            while case .loading = loadState {
                try await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
            }
            return try await _load() // Recursive call after loading completes
        case .loaded(let modelContainer):
            return modelContainer
        case .failed(let error):
            throw error
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
        defer {
            running = false
            Task { @MainActor in self.evaluationState = .idle }
        }

        do {
            logInfo("VLM generation started", category: .vision)
            let modelContainer = try await _load()
            let userInput = UserInput(prompt: .text(prompt), images: [.ciImage(CIImage(cvPixelBuffer: image))])

            let llmStart = Date()
            let state = GenerationState()

            let result = try await modelContainer.perform { context in
                Task { @MainActor in self.evaluationState = .processingPrompt }
                let input = try await context.processor.prepare(input: userInput)

                var switchedToGenerating = false
                let generateResult = try MLXLMCommon.generate(input: input, parameters: generateParameters, context: context) { tokens in
                    Task {
                        await state.markFirstToken(llmStartTime: llmStart)
                    }
                    if !switchedToGenerating {
                        switchedToGenerating = true
                        Task { @MainActor in self.evaluationState = .generatingResponse }
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

            logInfo(String(format: "VLM generation finished. TTFT: %.0f ms, tokens: %d, total: %.2f s (%.1f tok/s)", finalPromptDuration * 1000, finalTokenCount, totalTime, totalTime > 0 ? Double(finalTokenCount)/totalTime : 0), category: .vision)

            return VLMResult(
                description: finalOutput,
                timeToFirstToken: finalPromptDuration,
                totalGenerationTime: totalTime,
                tokensGenerated: finalTokenCount
            )

        } catch {
            logError(error, category: .vision)
            Task { @MainActor in self.evaluationState = .idle }
            return VLMResult(description: "Error: \(error.localizedDescription)", timeToFirstToken: 0, totalGenerationTime: 0, tokensGenerated: 0)
        }
    }
}
