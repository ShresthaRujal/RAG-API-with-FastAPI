# Personal AI Directory API

A multi-user Personal AI Directory built with **FastAPI, ChromaDB,
SQLite, and Ollama**.

The application allows users to upload text-based profiles, store
profile content as vector embeddings, ask questions about an individual
profile, and discover publicly available profiles through semantic
search.

The project uses a layered architecture with centralized routing and
separate controllers, services, repositories, schemas, and
configuration.

> **Current scope:** This is a local-first implementation with safer
> versioned profile updates. It does not yet include authentication,
> authorization, distributed coordination, or a complete production
> operations setup. See [Production and security
> considerations](#13-production-and-security-considerations).

------------------------------------------------------------------------

## 1. Features

-   Create profiles by uploading `.txt` files using multipart form data.
-   Update profiles using versioned storage, without deleting the
    currently active version first.
-   Retrieve and delete profiles.
-   Store profile chunks and embeddings in ChromaDB.
-   Track each profile's active version in SQLite.
-   Ask questions about a user's profile using Retrieval-Augmented
    Generation (RAG).
-   Search publicly available profiles using semantic search.
-   Configure paths, model names, and application settings through
    `.env`.
-   Explore and test endpoints through FastAPI Swagger UI.

## 2. Technology Stack

Technology           Purpose
  -------------------- ----------------------------------------------
Python               Main programming language
FastAPI              REST API framework
Uvicorn              ASGI application server
ChromaDB             Vector database and semantic retrieval
SQLite               Profile metadata and active-version manifest
Ollama               Local embedding and language model runtime
`nomic-embed-text`   Embedding model
`qwen2.5:0.5b`       Language model
Pydantic             Request and response validation
Pydantic Settings    Environment configuration
`python-multipart`   Multipart file upload support

SQLite is part of Python's standard library; it does not require a
separate database server.

------------------------------------------------------------------------

## 3. System Architecture

``` text
                         Client
                           |
                           v
                    FastAPI Application
                           |
                           v
                 Centralized API Router
                       /api/v1
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
    Profile Routes     Chat Routes     Directory Routes
          |                |                |
          v                v                v
    Controllers        Controllers      Controllers
          |                |                |
          v                v                v
     Services           Services         Services
          |                |                |
          +----------------+----------------+
                           |
                           v
                    Profile Repository
                           |
                +----------+----------+
                |                     |
                v                     v
             ChromaDB               SQLite
          Profile chunks       Active profile version
          and embeddings       and profile metadata
                |
                v
              Ollama
        Embedding and LLM models
```

### Architecture layers

#### Application layer

`main.py` initializes FastAPI, loads application settings, imports route
modules so they register their endpoints, and includes the shared API
router.

#### Router layer

The router layer organizes endpoints by feature. A single shared router
applies the `/api/v1` prefix to all API routes.

#### Controller layer

Controllers handle HTTP requests and responses. They parse multipart
uploads, validate request inputs, invoke services, and translate
application errors into HTTP responses.

Controllers do not contain database operations or core business logic.

#### Service layer

Services implement application use cases, such as creating, retrieving,
updating, and deleting profiles; answering profile questions; and
searching the public directory.

#### Repository layer

The repository manages persistence and retrieval. It coordinates
ChromaDB vector operations and SQLite profile-manifest operations.

#### Schema layer

Pydantic schemas define and validate application request and response
data.

#### Configuration layer

The configuration layer loads environment variables and provides
settings for application metadata, database paths, Ollama, embedding
models, and LLM models.

------------------------------------------------------------------------

## 4. Project Structure

``` text
RAG API with FastAPI/
│
├── .env
├── .gitignore
├── requirements.txt
├── README.md
│
├── chroma_db/
│   ├── profile_manifest.sqlite3   # Created at runtime
│   └── ChromaDB files             # Created at runtime
│
└── src/
    ├── main.py
    ├── config.py
    │
    ├── routers/
    │   ├── __init__.py
    │   ├── api_router.py
    │   ├── profile_routes.py
    │   ├── chat_routes.py
    │   └── directory_routes.py
    │
    ├── controllers/
    │   ├── __init__.py
    │   ├── profile_controller.py
    │   ├── chat_controller.py
    │   └── directory_controller.py
    │
    ├── services/
    │   ├── __init__.py
    │   ├── profile_service.py
    │   ├── chat_service.py
    │   └── directory_service.py
    │
    ├── repositories/
    │   ├── __init__.py
    │   └── profile_repository.py
    │
    └── schemas/
        ├── __init__.py
        ├── profile_schema.py
        ├── chat_schema.py
        └── directory_schema.py
```

### Important files and directories

Path              Responsibility
  ----------------- --------------------------------------------------
`src/main.py`     FastAPI application entry point
`src/config.py`   Environment-based application settings
`routers/`        Shared API router and feature route registration
`controllers/`    HTTP request handling and response mapping
`services/`       Business logic and RAG orchestration
`repositories/`   ChromaDB and SQLite persistence operations
`schemas/`        Pydantic data models
`.env`            Local environment configuration
`chroma_db/`      ChromaDB persistence and SQLite manifest

The `chroma_db/` directory is runtime data. Do not commit database files
to source control.

------------------------------------------------------------------------

## 5. Profile Upload and Storage

Profile creation and updates accept a `.txt` file using
`multipart/form-data`.

### Profile fields

Field         Type                 Required
  ------------- -------------------- -------------------------
`user_id`     URL path parameter   Yes
`full_name`   Form text            Yes
`is_public`   Form boolean         No; defaults to `false`
`file`        `.txt` file          Yes

The uploaded file is decoded as UTF-8 (with an optional UTF-8 BOM) and
its text becomes the profile content.

The current controller implementation enforces: - `.txt` file
extension. - Non-empty file content. - UTF-8 text encoding. - A maximum
file size of 2 MB.

### Versioned profile replacement

The repository uses two persistence systems for different
responsibilities:

-   **ChromaDB:** Stores versioned document chunks and their embeddings.
-   **SQLite:** Stores profile metadata and the active version
    identifier.

When a profile is created or updated:

1.  Generate a unique profile version ID.
2.  Split the incoming content into chunks.
3.  Insert the new chunks into ChromaDB using the new version ID.
4.  Verify that the expected chunks were stored.
5.  Switch the active version in SQLite inside a SQLite write
    transaction.
6.  Keep the previous version temporarily so it can be cleaned up later.

The previous active version is not deleted before the new version is
inserted and verified.

``` text
                  Uploaded TXT file
                          |
                          v
                    Read and validate
                          |
                          v
                    Split into chunks
                          |
                          v
                 Generate version ID
                          |
                          v
                  Insert into ChromaDB
                          |
                          v
                   Verify new chunks
                          |
                          v
              Switch active version in SQLite
                          |
                          v
                  New version is active
                          |
                          v
                Retain old version temporarily
                          |
                          v
                 Scheduled old-version cleanup
```

If insertion or verification fails, the repository attempts to remove
only the newly created version. The previous active version remains
unchanged.

The SQLite transaction makes the active-version pointer update atomic.
It does **not** make SQLite and ChromaDB a single distributed
transaction.

------------------------------------------------------------------------

## 6. RAG Workflow

The application uses Retrieval-Augmented Generation (RAG) to answer
questions using stored profile information.

### Profile ingestion

``` text
TXT Profile
    |
    v
Text Validation
    |
    v
Text Chunking
    |
    v
Ollama Embedding Model
    |
    v
Vector Embeddings
    |
    v
ChromaDB Storage
    |
    v
SQLite Active-Version Manifest
```

### Personal question answering

``` text
User Question
      |
      v
Read Active Profile Version
      |
      v
Semantic Search in ChromaDB
      |
      v
Retrieve Relevant Profile Chunks
      |
      v
Build Contextual Prompt
      |
      v
Ollama Language Model
      |
      v
Generated Answer
```

Personal searches are restricted to the active version of the requested
user's profile.

### Public directory search

The directory search uses the SQLite manifest to identify public
profiles and their active versions. ChromaDB is then queried against
those active public versions. Results are deduplicated by user ID.

------------------------------------------------------------------------

## 7. API Endpoints

All endpoints use the shared prefix:

``` text
/api/v1
```

### Profile management

  -----------------------------------------------------------------------------
Method            Endpoint                Request format    Description
  ----------------- ----------------------- ----------------- -----------------
POST              `/profiles/{user_id}`   Multipart form    Create a profile
from a TXT file

GET               `/profiles/{user_id}`   No body           Retrieve a
profile

PUT               `/profiles/{user_id}`   Multipart form    Replace a profile
using a new TXT
file

DELETE            `/profiles/{user_id}`   No body           Delete a profile
-----------------------------------------------------------------------------

### Personal AI chat

  -----------------------------------------------------------------------------
Method            Endpoint                Request format    Description
  ----------------- ----------------------- ----------------- -----------------
POST              `/chat/{user_id}/ask`   JSON              Ask a question
using the user's
profile

  -----------------------------------------------------------------------------

### Public directory

  ---------------------------------------------------------------------------
Method            Endpoint              Request format    Description
  ----------------- --------------------- ----------------- -----------------
POST              `/directory/search`   JSON              Search public
profiles
semantically

  ---------------------------------------------------------------------------

------------------------------------------------------------------------

## 8. API Examples

### Create a profile

**POST** `/api/v1/profiles/rujal`

``` bash
curl -X POST "http://127.0.0.1:8000/api/v1/profiles/rujal" \
  -F "full_name=Rujal Shrestha" \
  -F "is_public=true" \
  -F "file=@Rujal_Shrestha_Resume.txt"
```

### Update a profile

**PUT** `/api/v1/profiles/rujal`

``` bash
curl -X PUT "http://127.0.0.1:8000/api/v1/profiles/rujal" \
  -F "full_name=Rujal Shrestha" \
  -F "is_public=true" \
  -F "file=@updated_resume.txt"
```

The update replaces the profile content with the contents of the newly
uploaded file. The old active version is retained temporarily.

### Retrieve a profile

**GET** `/api/v1/profiles/rujal`

``` bash
curl "http://127.0.0.1:8000/api/v1/profiles/rujal"
```

### Delete a profile

**DELETE** `/api/v1/profiles/rujal`

``` bash
curl -X DELETE "http://127.0.0.1:8000/api/v1/profiles/rujal"
```

The repository removes the active profile manifest entry. Physical
vector cleanup should be handled by a maintenance process.

### Ask a profile question

**POST** `/api/v1/chat/rujal/ask`

``` bash
curl -X POST "http://127.0.0.1:8000/api/v1/chat/rujal/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What backend technologies does this developer know?"
  }'
```

### Search the public directory

**POST** `/api/v1/directory/search`

``` bash
curl -X POST "http://127.0.0.1:8000/api/v1/directory/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Find developers experienced in React"
  }'
```

------------------------------------------------------------------------

## 9. Environment Configuration

Create a `.env` file in the project root:

``` env
APP_NAME="Personal AI Directory"
APP_VERSION="1.0.0"
DEBUG=true

CHROMA_PATH="./chroma_db"
COLLECTION_NAME="personal_profiles"

OLLAMA_URL="http://localhost:11434"

EMBEDDING_MODEL="nomic-embed-text"
LLM_MODEL="qwen2.5:0.5b"

TOP_K=3
```

The configuration is loaded through Pydantic Settings.

The SQLite manifest is created automatically inside the configured
ChromaDB directory:

``` text
chroma_db/profile_manifest.sqlite3
```

Do not commit `.env`, database files, or private profile content to
version control.

------------------------------------------------------------------------

## 10. Installation and Setup

### Prerequisites

-   Python 3.11 or a compatible version supported by the installed
    dependencies.
-   Ollama.
-   Git (optional).

### Step 1: Open the project

``` bash
cd "RAG API with FastAPI"
```

### Step 2: Create and activate a virtual environment

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install dependencies

``` bash
pip install -r requirements.txt
```

Make sure `requirements.txt` includes:

``` text
fastapi
uvicorn[standard]
chromadb
ollama
pydantic
pydantic-settings
python-dotenv
python-multipart
```

SQLite is included with Python and does not need a pip package.

### Step 4: Install Ollama models

``` bash
ollama pull nomic-embed-text
ollama pull qwen2.5:0.5b
```

### Step 5: Start Ollama

``` bash
ollama serve
```

Keep Ollama running.

### Step 6: Start FastAPI

Open another terminal, activate the virtual environment, and run:

``` bash
python -m uvicorn main:app --app-dir src --reload
```

The API is available at:

``` text
http://127.0.0.1:8000
```

------------------------------------------------------------------------

## 11. API Documentation

FastAPI automatically generates interactive API documentation.

Documentation   URL
  --------------- -------------------------------
Swagger UI      `http://127.0.0.1:8000/docs`
ReDoc           `http://127.0.0.1:8000/redoc`
Root endpoint   `http://127.0.0.1:8000/`

Use Swagger UI to upload TXT files and test the endpoints.

For profile creation and updates, Swagger should show a multipart form
containing `full_name`, `is_public`, and `file`.

------------------------------------------------------------------------

## 12. Version Cleanup and Maintenance

Inactive profile versions are retained temporarily. The repository
exposes:

``` python
repository.cleanup_old_versions(
    user_id="rujal",
    retention_seconds=86400,
)
```

This removes inactive versions older than the configured retention
period for that user. The default retention period is 24 hours.

Run cleanup from a single scheduled maintenance worker. Do not run
independent cleanup jobs in every API worker.

A production maintenance process should also: - Enumerate users that
have inactive versions. - Retry failed cleanup operations. - Log cleanup
failures and orphaned versions. - Monitor ChromaDB and SQLite storage. -
Verify database backups and restore procedures.

The repository method is a maintenance primitive; it does not schedule
itself.

------------------------------------------------------------------------

## 13. Production and Security Considerations

The versioned update strategy reduces the risk of losing the previous
profile when a new ChromaDB insertion or verification fails. However, it
is not by itself a complete production deployment.

### Data consistency

-   SQLite and ChromaDB do not share a transaction.
-   A process crash between ChromaDB insertion and SQLite activation can
    leave orphaned chunks.
-   A process crash after activation but before cleanup can leave old
    versions behind.
-   A reconciliation job should detect and repair orphaned or missing
    versions.
-   Back up the ChromaDB directory and SQLite manifest together from a
    consistent snapshot.

### Deployment

-   Use a single maintenance worker for old-version cleanup.
-   Configure persistent storage for both ChromaDB and SQLite.
-   Use controlled migrations and backups when changing the manifest
    schema.
-   Add monitoring, structured logs, health checks, and automated tests.
-   Test recovery behavior after interrupted writes and process
    restarts.

### Security

This implementation does not include authentication or authorization.

User IDs are identifiers, not credentials. Anyone who can access the API
may be able to read, update, or delete profiles if they know or guess
the IDs.

Do not expose this API publicly with private profile data until
authentication, authorization, ownership checks, transport security, and
appropriate operational controls are implemented.

------------------------------------------------------------------------

## 14. Design Principles

-   **Single Responsibility:** Each layer has a clear responsibility.
-   **Separation of Concerns:** HTTP handling, business logic, and
    persistence are separated.
-   **Centralized Routing:** API versioning is managed in one shared
    router.
-   **Reusability:** Services and repositories can be reused.
-   **Versioned Writes:** New profile versions are stored and verified
    before activation.
-   **Atomic Manifest Updates:** SQLite transactions protect
    active-version pointer changes.
-   **Configuration Management:** Environment-specific settings are
    externalized.
-   **Local AI:** Embedding and language models run locally through
    Ollama.

------------------------------------------------------------------------

## 15. Future Improvements

-   Authentication and authorization.
-   Profile ownership and access control.
-   PostgreSQL for multi-instance or larger-scale metadata management.
-   A durable background job system for cleanup and reconciliation.
-   Conversation history.
-   PDF and additional document formats.
-   Improved document chunking and metadata filtering.
-   Multiple embedding models.
-   Rate limiting and request-size controls.
-   Automated tests and CI/CD.
-   Docker deployment and observability.

------------------------------------------------------------------------

## 16. License

This project is currently intended for learning, experimentation, and
development.

Add an appropriate open-source license before distributing it publicly.
