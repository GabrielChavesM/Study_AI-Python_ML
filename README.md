# StudyAI - Python ML Quiz Application

StudyAI is a Python-based application designed to help users learn and test their knowledge through interactive quizzes. The app uses AI-powered question generation and text-to-speech functionality to enhance the learning experience.

## Features

- **AI-Powered Question Generation**: Automatically generates multiple-choice questions based on selected topics and difficulty levels.
- **Text-to-Speech (TTS)**: Reads questions and explanations aloud using a speech synthesis engine. Questions and answers are read asynchronously as soon as they appear in the interface.
- **Interactive GUI**: Built with `customtkinter` for a modern and user-friendly interface.
- **Progress Tracking**: Tracks your quiz progress and calculates your accuracy.
- **History Management**: Saves quiz history in JSON format for future reference.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/StudyAI.git
   cd StudyAI
   ```

2. Install the required dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

3. Ensure you have Python 3.12.3 installed (recommended).

## Usage

1. Run the application:
   ```bash
   python3 script.py
   ```

2. Select a topic and difficulty level from the dropdown menus.

3. The app will automatically read the questions and answers aloud as they appear in the interface.

4. Track your progress using the progress bar and accuracy label.

## Dependencies

The application requires the following Python libraries:

- `customtkinter`
- `groq`
- `python-dotenv`
- `pyttsx3`
- `Pillow`

Install them using the `requirements.txt` file.

## Environment Variables

Create a `.env` file in the project directory and add your Groq API key:
```
GROQ_API_KEY=your_api_key_here
```

## Folder Structure

- `prompts/`: Contains text files with base prompts for question generation.
- `historicos/`: Stores quiz history in JSON format.

## Updates

- **Asynchronous TTS**: Questions and answers are now read aloud automatically as they appear, without requiring user input.
- **Improved TTS Handling**: Text-to-speech functionality is now fully asynchronous and non-blocking, ensuring smooth operation of the GUI.

## Future Improvements

- Enhance question generation with more diverse topics and models.
- Improve the GUI with additional customization options.

## License

This project is licensed under the MIT License.

## Author

Gabriel Chaves