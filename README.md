# Orion Live

**Open-source AI agent for real-time vision & voice tasks with a focus on performance and speed**

Orion Live is a multimodal AI assistant that combines webcam vision and voice interaction using Google's Gemini 2.0 Flash model. It captures images from your webcam, records audio questions, and provides intelligent responses based on both visual and audio context.

## Features

- 🎥 **Real-time webcam capture** - Automatically captures images from your webcam
- 🎤 **Voice interaction** - Record questions and get spoken responses
- 🧠 **Gemini 2.0 Flash integration** - Uses Google's latest multimodal AI model
- 🔊 **Text-to-speech** - Spoken responses using pyttsx3
- 🔄 **Interactive loop** - Continuous conversation mode
- 🧹 **Automatic cleanup** - Manages temporary files and uploads

## Prerequisites

- Python 3.8 or higher
- Webcam access
- Microphone access
- Google API key for Gemini

## Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd orion-live
```

2. **Install dependencies:**
```bash
pip install google-genai opencv-python sounddevice scipy pillow pyttsx3
```

3. **Set up your Google API key:**
```bash
export GOOGLE_API_KEY='your_api_key_here'
```

Get your API key from: https://makersuite.google.com/app/apikey

## Usage

### Basic Usage

1. **Test your setup:**
```bash
python test_gemini.py
```

2. **Run the main application:**
```bash
python main.py
```

3. **Follow the prompts:**
   - Press Enter when ready to record
   - Speak your question for 7 seconds
   - Wait for the AI response
   - Choose to continue or exit

### Configuration

Edit the configuration variables in `main.py`:

```python
# Audio recording parameters
AUDIO_DURATION_SECONDS = 7  # Recording duration
AUDIO_SAMPLE_RATE = 44100   # Audio quality
WEBCAM_INDEX = 0            # Webcam device index
```

## How It Works

1. **Image Capture**: Takes a snapshot from your webcam
2. **Audio Recording**: Records your voice question for 7 seconds
3. **File Upload**: Uploads audio to Gemini API
4. **AI Processing**: Gemini 2.0 Flash analyzes both image and audio
5. **Response**: Receives text response and converts to speech
6. **Cleanup**: Removes temporary files automatically

## Troubleshooting

### Common Issues

**Import errors:**
```bash
pip install --upgrade google-genai
```

**Webcam not found:**
- Check if another application is using the webcam
- Try changing `WEBCAM_INDEX` to 1 or 2
- Ensure webcam permissions are granted

**Audio recording issues:**
- Check microphone permissions
- Verify `sounddevice` can access your microphone:
```python
import sounddevice as sd
print(sd.query_devices())
```

**TTS not working:**
- On macOS: TTS should work out of the box
- On Linux: Install espeak: `sudo apt-get install espeak`
- On Windows: Should work with built-in SAPI

**API errors:**
- Verify your API key is correct
- Check if you have Gemini API access
- Ensure you're not exceeding rate limits

### Debug Mode

Enable more verbose output by adding debug prints or checking:
- Audio file creation and size
- Image capture success
- API response details

## API Costs

Gemini 2.0 Flash pricing (as of 2024):
- Text input: Free up to rate limits
- Image input: Check current Google AI pricing
- Audio input: Check current Google AI pricing

Monitor your usage in the Google AI Studio.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
- Check the troubleshooting section above
- Review Google AI documentation
- Open an issue in this repository

## Changelog

### v1.0.0
- Initial release with Gemini 2.0 Flash
- Multimodal vision and voice interaction
- Real-time webcam capture
- Text-to-speech responses