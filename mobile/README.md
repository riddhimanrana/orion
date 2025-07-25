# Orion Live - iOS App

Orion Live is the iOS app designed to work seamlessly with the Orion architecture and backend services.

## Requirements

- Xcode 16 or later  
- iOS 18.0 or later  
- Swift 5.8 or later  

## Frameworks

- SwiftUI for building the user interface  
- CoreML for on-device machine learning  
- Combine for reactive data binding  
- URLSession for networking  

## Deployment Target

- iPhone 12 and newer devices running iOS 18+

## Getting Started

1. Clone the repository:  

   ```bash
   git clone https://github.com/your-org/orion-mobile.git
   cd orion-mobile/Orion
   ```

2. Download the YOLO11N and custom fine-tuned FastVLM coreml models:  

   ```bash
   sh setup_models.sh
   ```

3. Open the project in Xcode:  

   ```bash
   open Orion.xcodeproj
   ```

## Configuration

The file `Orion-Info.plist` contains my auth endpoints and keys.

These values are safe to share. Feel free to replace them with your own database or authentication endpoints.

In addition, the folder `Configuration/Build.xconfig` contains a `DISAMBIGUATOR` configuration to make it easier to build and run a sample code project. Once you set your project's development team, you'll have a unique bundle identifier.

## Running the App

- Select a simulator or device in Xcode  
- Press `⌘`+`R` or click **Run**
