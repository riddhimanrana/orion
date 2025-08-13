import SwiftUI
import Combine

struct OTPInputView: View {
    @Binding var code: String
    let numberOfFields: Int = 6
    @FocusState private var focusedField: Int?

    var body: some View {
        VStack {
            ZStack {
                // Hidden text field to handle keyboard input
                TextField("", text: $code)
                    .frame(width: 0, height: 0)
                    .opacity(0)
                    .focused($focusedField, equals: 0) // Always keep focus on the hidden field
                    .onChange(of: code) { newValue in
                        // Limit to the number of fields and only allow numeric input
                        let filtered = newValue.filter { $0.isNumber }
                        if filtered.count > numberOfFields {
                            code = String(filtered.prefix(numberOfFields))
                        } else {
                            code = filtered
                        }
                    }

                // The visible boxes
                HStack(spacing: 10) {
                    ForEach(0..<numberOfFields, id: \.self) { index in
                        ZStack {
                            Rectangle()
                                .stroke(focusedField == 0 && index == code.count ? Color.accentColor : Color.gray.opacity(0.5), lineWidth: 2)
                                .frame(width: 40, height: 50)
                                .cornerRadius(8)
                                .background(Color(NSColor.controlBackgroundColor))
                            
                            if index < code.count {
                                let charIndex = code.index(code.startIndex, offsetBy: index)
                                Text(String(code[charIndex]))
                                    .font(.system(size: 24, weight: .bold, design: .monospaced))
                            }
                        }
                    }
                }
            }
            .onTapGesture {
                // Focus the hidden text field when any part of the view is tapped
                focusedField = 0
            }
            .onAppear {
                // Set initial focus
                focusedField = 0
            }
        }
    }
}
