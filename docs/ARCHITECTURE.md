# Architecture

User

↓

AI Coach

↓

Analysis Engine

↓

Database

↓

Data Collection Layer

↓

Strava / Garmin

## Components

### Data Collection

Responsibilities:

- Fetch activities

- Normalize data

### Database

Responsibilities:

- Store activities

- Store user data

### Analysis Engine

Responsibilities:

- Calculate metrics

- Detect trends

### AI Layer

Responsibilities:

- Explain results

- Generate recommendations

### Memory Layer

Responsibilities:

- Store long-term context

## Current Backend Structure

```text
src/running_agent/
├── database.py
├── models/
│   └── activity.py
├── repositories/
│   └── activity_repository.py
└── services/
    └── activity_service.py