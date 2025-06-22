# StudyAI - Python ML Quiz Application

StudyAI is a Python-based application designed to help users learn and test their knowledge through interactive quizzes. The app uses AI-powered question generation, text-to-speech functionality, and a modern GUI to enhance the learning experience.

## Features

- **AI-Powered Question Generation**: Automatically generates multiple-choice questions based on selected topics, difficulty levels, and language preferences.
- **Multilingual Support**: Allows users to choose between Portuguese and English for questions, answers, and explanations.
- **Text-to-Speech (TTS)**: Reads questions, answers, and explanations aloud using a speech synthesis engine. The TTS adapts to the selected language and operates asynchronously.
- **Interactive GUI**: Built with `customtkinter` for a modern and user-friendly interface, including dropdown menus for topic, difficulty, and language selection.
- **Dark/Light Mode**: Users can toggle between dark and light modes for a personalized interface experience.
- **Sound Control**: Users can enable or disable sound for TTS functionality.
- **Progress Tracking**: Tracks quiz progress in real-time, displaying the user's accuracy and completion percentage through a progress bar and label.
- **Answer Validation**: Ensures users can only submit valid answers (A, B, C, or D) and blocks new responses while the system explains the previous question.
- **Feedback Generation**: Provides detailed feedback at the end of the quiz, including an analysis of correct and incorrect answers, themes to improve, study suggestions, and motivational messages.
- **History Management**: Saves quiz history in JSON and TXT formats, allowing users to review their performance and analyze areas for improvement.
- **Customizable Question Flow**: Generates questions dynamically based on user-selected topics and difficulty levels, ensuring no repetition within the same quiz.
- **Speech Recognition**: Allows users to respond to questions using voice input, enhancing accessibility.
- **Error Handling**: Includes robust error handling for API calls, TTS functionality, and file operations.
- **Scalability**: Designed with modular architecture to support future expansions, such as new topics, languages, and integration with educational platforms.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/GabrielChavesM/StudyAI.git
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

2. Select a topic, difficulty level, and language from the dropdown menus.

3. Optionally, toggle sound and dark/light mode preferences.

4. Start the quiz and answer questions using the input field or voice recognition.

5. Track your progress using the progress bar and accuracy label.

6. At the end of the quiz, review detailed feedback and access your performance history.

## Dependencies

The application requires the following Python libraries:

- `customtkinter`
- `groq`
- `python-dotenv`
- `pyttsx3`
- `speechrecognition`
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
- `historicos_gerais/`: Consolidates overall performance history in TXT format.

## Updates

- **Multilingual Support**: Added support for Portuguese and English, adapting all questions, answers, and explanations to the selected language.
- **Enhanced Feedback System**: Generates detailed feedback, including themes to improve, study suggestions, and motivational messages.
- **Improved TTS Handling**: Text-to-speech functionality is now fully asynchronous and non-blocking, ensuring smooth operation of the GUI.
- **History Selection**: Users can choose which history file to view from a list of available topics.

## Future Improvements

- Expand question generation to include more diverse topics and advanced models.
- Add gamification elements, such as achievements and rewards, to enhance user engagement.
- Integrate with educational platforms like Moodle or Google Classroom for broader accessibility.
- Introduce offline mode for users without internet access.

## License

This project is licensed under the MIT License.

## Author

Gabriel Chaves