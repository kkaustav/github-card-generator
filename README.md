# GitHub Dev Card Generator

An AI-powered web application that generates premium, personalized developer showcase cards from public GitHub profiles. It uses Gemini 2.5 Flash to analyze a user's GitHub activity, repositories, and languages to infer their "Developer Vibe", top skills, and a fun fact.

## 🚀 Live Application

**[Access the Live App Here](https://github-card-frontend-675769433571.us-central1.run.app)**

You do **not** need to run anything locally to use the app! It is fully hosted in the cloud. Just open the link above, enter a GitHub username, and hit generate.

## 🏗️ Architecture & Infrastructure

The application is a fully serverless architecture deployed on **Google Cloud Platform (GCP)** using Cloud Run, billed to a GCP Trial Account.

```mermaid
graph TD
    User([User / Browser]) -->|HTTPS| Frontend[Cloud Run: Frontend Service]
    Frontend -->|POST /generate| Backend[Cloud Run: Backend Service]
    
    subgraph GCP [Google Cloud Platform - us-central1]
        Frontend
        
        subgraph Backend Container
            Backend[FastAPI App] -->|Instantiates| Agent[Google ADK Agent]
            Agent -->|Stdio MCP| MCPServer[MCP Tool Server]
        end
    end
    
    MCPServer -->|REST API| GitHubAPI[(GitHub REST API)]
    MCPServer -->|Application Default Credentials| VertexAI[(Google Cloud Vertex AI)]
    
    classDef gcp fill:#e8f0fe,stroke:#4285f4,stroke-width:2px,color:#1967d2
    classDef container fill:#fce8e6,stroke:#ea4335,stroke-width:2px,color:#a50e0e
    classDef external fill:#f6f8fa,stroke:#24292f,stroke-width:2px,color:#24292f
    
    class Frontend,Backend,Agent,MCPServer,VertexAI gcp
    class GitHubAPI external
```

### Core Components:
1.  **Frontend Service**: A static HTML/JS UI deployed via Docker (NGINX) to Cloud Run. It directly calls the backend Cloud Run service.
2.  **Backend Service**: A FastAPI Python application deployed to Cloud Run.
3.  **ADK Agent**: Orchestrates the tool calls using the Google Agentic Development Kit.
4.  **MCP Server**: Implements the Model Context Protocol tools to:
    *   Fetch rich data (repos, languages, stats) via the GitHub API.
    *   Analyze the profile using Google Cloud Vertex AI (Gemini 2.5 Flash) to extract insights.
    *   Generate the final HTML card with a premium, compact design.

### 🎁 Bonus Feature: Vertex AI Memory Bank
This project implements the **Vertex AI Memory Bank** upgrade.
We replaced the default `InMemorySessionService` with `VertexAiSessionService` and `VertexAiMemoryBankService` in `main.py`. This ensures that session state and user preferences are persistently backed by Google Cloud's enterprise-grade infrastructure instead of volatile in-memory storage, allowing the agent to continuously learn and recall insights across different generating sessions.

## 💻 Local Development Workflow

If you want to modify the code and test it locally on your Mac:

1.  **Start the Backend**:
    Open your macOS terminal and run:
    ```bash
    cd /Users/kaustubhkar/.gemini/antigravity/scratch/github-card-generator/backend
    uvicorn main:app --reload --port 8080
    ```
2.  **Test the Local Server**:
    The backend will run on `http://localhost:8080`. 
    *(Note: Your frontend `index.html` is currently hardcoded to point to the live Cloud Run backend. If you want to test the full flow locally, you would need to temporarily change `API_BASE` in `frontend/index.html` back to `http://localhost:8080` and open the HTML file in your browser).*

## 🔑 Infrastructure & Scaling Details

*   **Hosting**: Both frontend and backend are deployed as Google Cloud Run services.
*   **Scaling**: Configured to scale down to `0` instances when not in use (costing $0) and up to a maximum of `5` instances under load.
*   **Docker Registry**: Images are stored in Google Artifact Registry (`us-central1-docker.pkg.dev`).
*   **APIs**:
    *   **Vertex AI**: Bypasses AI Studio API keys completely. Cloud Run uses Application Default Credentials (ADC) to securely authenticate with GCP Vertex AI, eliminating 20/day quotas and billing seamlessly to the GCP project.
    *   **GitHub**: Uses a Personal Access Token to avoid unauthenticated API rate limits.
