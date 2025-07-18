//
// For licensing see accompanying LICENSE file.
// Copyright (C) 2025 Apple Inc. All Rights Reserved.
//

import CoreImage
import FastVLM
import Foundation
import MLX
import MLXLMCommon
import MLXRandom
import MLXVLM

@Observable
@MainActor
class FastVLMModel {

    public var running = false
    public var modelInfo = ""
    public var output = ""
    public var promptTime: String = ""

    enum LoadState {
        case idle
        case loaded(ModelContainer)
    }

    private let modelConfiguration = FastVLM.modelConfiguration

    /// parameters controlling the output
    let generateParameters = GenerateParameters(temperature: 0.0)
    let maxTokens = 240

    /// update the display every N tokens -- 4 looks like it updates continuously
    /// and is low overhead.  observed ~15% reduction in tokens/s when updating
    /// on every token
    let displayEveryNTokens = 4

    private var loadState = LoadState.idle
    private var currentTask: Task<Void, Never>?

    enum EvaluationState: String, CaseIterable {
        case idle = "Idle"
        case processingPrompt = "Processing Prompt"
        case generatingResponse = "Generating Response"
    }

    public var evaluationState = EvaluationState.idle

    public init() {
        FastVLM.register(modelFactory: VLMModelFactory.shared)
    }

    private func _load() async throws -> ModelContainer {
        switch loadState {
        case .idle:
            // limit the buffer cache
            MLX.GPU.set(cacheLimit: 20 * 1024 * 1024)

            let modelContainer = try await VLMModelFactory.shared.loadContainer(
                configuration: modelConfiguration
            ) {
                [modelConfiguration] progress in
                Task { @MainActor in
                    self.modelInfo =
                        "Downloading \(modelConfiguration.name): \(Int(progress.fractionCompleted * 100))%"
                }
            }
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
        } catch {
            self.modelInfo = "Error loading model: \(error)"
        }
    }

    public func generate(_ userInput: UserInput) async -> Task<Void, Never> {
        if let currentTask, running {
            return currentTask
        }

        running = true
        
        // Cancel any existing task
        currentTask?.cancel()

        // Create new task and store reference
        let task = Task {
            // Reset stats for the new generation
            self.promptTime = ""
            
            do {
                let modelContainer = try await _load()

                // each time you generate you will get something new
                MLXRandom.seed(UInt64(Date.timeIntervalSinceReferenceDate * 1000))
                
                // Check if task was cancelled
                if Task.isCancelled { return }

                let result = try await modelContainer.perform { context in
                    // Measure the time it takes to prepare the input
                    
                    Task { @MainActor in
                        evaluationState = .processingPrompt
                    }

                    // MODIFIED: Add variables to track timing throughout the generation
                    let llmStart = Date()
                    var promptDuration: TimeInterval = 0
                    var generationStartTime: Date?
                    
                    let input = try await context.processor.prepare(input: userInput)
                    
                    var seenFirstToken = false

                    // FastVLM generates the output
                    let generateResult = try MLXLMCommon.generate(
                        input: input, parameters: generateParameters, context: context
                    ) { tokens in
                        // Check if task was cancelled
                        if Task.isCancelled {
                            return .stop
                        }

                        // This block runs when the first token is received
                        if !seenFirstToken {
                            seenFirstToken = true
                            
                            // MODIFIED: Mark the time of the first token and calculate prompt processing duration
                            generationStartTime = Date()
                            promptDuration = generationStartTime!.timeIntervalSince(llmStart)
                            
                            let text = context.tokenizer.decode(tokens: tokens)
                            Task { @MainActor in
                                evaluationState = .generatingResponse
                                self.output = text
                                // Initially, display just the prompt time
                                self.promptTime = String(format: "%.0f ms", promptDuration * 1000)
                            }
                        }

                        // Show the text in the view as it generates
                        if tokens.count % displayEveryNTokens == 0 {
                            let text = context.tokenizer.decode(tokens: tokens)
                            Task { @MainActor in
                                self.output = text
                            }
                        }

                        if tokens.count >= maxTokens {
                            return .stop
                        } else {
                            return .more
                        }
                    }
                    
                    // MODIFIED: After generation is complete, calculate tokens/second
                    if let startTime = generationStartTime, generateResult.tokens.count > 1 {
                        let generationDuration = Date().timeIntervalSince(startTime)
                        // The number of tokens generated after the first one
                        let tokensGenerated = Double(generateResult.tokens.count - 1)
                        if generationDuration > 0 {
                            let tokensPerSecond = tokensGenerated / generationDuration
                            // Update the UI on the main thread with the combined stats
                            Task { @MainActor in
                                let promptString = String(format: "%.0f ms", promptDuration * 1000)
                                let generationString = String(format: "%.1f tok/s", tokensPerSecond)
                                self.promptTime = "\(promptString), \(generationString)"
                            }
                        }
                    }
                    
                    return generateResult
                }
                
                // Check if task was cancelled before updating UI
                if !Task.isCancelled {
                    self.output = result.output
                }

            } catch {
                if !Task.isCancelled {
                    output = "Failed: \(error)"
                }
            }

            if evaluationState == .generatingResponse {
                evaluationState = .idle
            }

            running = false
        }
        
        currentTask = task
        return task
    }
    
    public func cancel() {
        currentTask?.cancel()
        currentTask = nil
        running = false
        output = ""
        promptTime = ""
    }
}
