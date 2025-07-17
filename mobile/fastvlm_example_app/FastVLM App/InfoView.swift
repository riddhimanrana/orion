//
// For licensing see accompanying LICENSE file.
// Copyright (C) 2025 Apple Inc. All Rights Reserved.
//

import Foundation
import SwiftUI

struct InfoView: View {
    @Environment(\.dismiss) var dismiss

    let paragraph1 = "**FastVLM¹** is a new family of Vision-Language models that makes use of **FastViTHD**, a hierarchical hybrid vision encoder that produces small number of high quality tokens at low latencies, resulting in significantly faster time-to-first-token (TTFT)."
    let paragraph2 = "This app showcases the **FastVLM** model in action, allowing users to freely customize the prompt. FastVLM utilizes Qwen2-Instruct LLMs without additional safety tuning, so please exercise caution when modifying the prompt."
    let footer = "1. **FastVLM: Efficient Vision Encoding for Vision Language Models.** (CVPR 2025) Pavan Kumar Anasosalu Vasu, Fartash Faghri, Chun-Liang Li, Cem Koc, Nate True, Albert Antony, Gokul Santhanam, James Gabriel, Peter Grasch, Oncel Tuzel, Hadi Pouransari"

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20.0) {
                // I'm not going to lie, this doesn't make sense...
                // Wrapping `String`s with `.init()` turns them into `LocalizedStringKey`s
                // which gives us all of the fun Markdown formatting while retaining the
                // ability to use `String` variables. ¯\_(ツ)_/¯
                Text("\(.init(paragraph1))\n\n\(.init(paragraph2))\n\n")
                    .font(.body)

                Spacer()

                Text(.init(footer))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding()
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            .textSelection(.enabled)
            .navigationTitle("Information")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                #if os(iOS)
                ToolbarItem(placement: .navigationBarLeading) {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle")
                            .resizable()
                            .frame(width: 25, height: 25)
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                }
                #elseif os(macOS)
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") {
                        dismiss()
                    }
                    .buttonStyle(.bordered)
                }
                #endif
            }
        }
    }
}

#Preview {
    InfoView()
}
