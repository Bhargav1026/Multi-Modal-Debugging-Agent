# Multi-Modal Debugging Agent

## Overview
The Multi-Modal Debugging Agent is a project designed to facilitate debugging across multiple modalities. It provides a backend service that handles API requests, orchestrates various components, and manages data models and worker processes. Additionally, it includes a VS Code extension to enhance the debugging experience.

## Project Structure
The project is organized into several key directories:

- **backend/**: Contains the backend application code.
  - **app/**: The main application logic, including:
    - **api/**: Modules for handling API requests and responses.
    - **orchestration/**: Logic for coordinating different components.
    - **models/**: Data models defining the structure of the application data.
    - **workers/**: Background tasks and asynchronous processing.
  - **tests/**: Unit and integration tests for the backend application.
  - **main.py**: The entry point for the backend application.
  - **requirements.txt**: Lists dependencies required for the backend.
  - **.env.example**: Example environment variables for configuration.

- **extension/**: Contains the VS Code extension code.
  - **src/**: The source code for the extension.
  - **package.json**: Configuration file for the extension.
  - **tsconfig.json**: TypeScript configuration file.
  - **README.md**: Documentation specific to the extension.

- **sandbox/**: Contains files for Docker containerization.
  - **Dockerfile**: Instructions for building the Docker image.
  - **entrypoint.sh**: Shell script for the Docker container entry point.

- **docs/**: Documentation files.
  - **API.md**: API documentation detailing endpoints and usage.
  - **INCIDENT_REPORT_TEMPLATE.md**: Template for reporting incidents.

## Getting Started
To get started with the Multi-Modal Debugging Agent, follow these steps:

1. **Clone the Repository**
   ```
   git clone <repository-url>
   cd Multi-Modal-Debugging-Agent
   ```

2. **Set Up the Backend**
   - Navigate to the `backend` directory.
   - Install the required dependencies:
     ```
     pip install -r requirements.txt
     ```
   - Configure environment variables by copying `.env.example` to `.env` and updating the values as needed.

3. **Run the Backend**
   ```
   python main.py
   ```

4. **Set Up the Extension**
   - Navigate to the `extension` directory.
   - Install the necessary dependencies:
     ```
     npm install
     ```
   - Open the extension in your preferred code editor and follow the instructions in `README.md` for usage.

5. **Run the Sandbox**
   - Build the Docker image:
     ```
     docker build -t multi-modal-debugging-agent .
     ```
   - Run the Docker container:
     ```
     docker run multi-modal-debugging-agent
     ```

## Contributing
Contributions are welcome! Please read the [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines on how to contribute to this project.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.