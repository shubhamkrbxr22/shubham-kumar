# 🤖 AI Resume Shortlisting & Candidate Evaluation System

A scalable AI-powered backend system that evaluates resumes against job descriptions, scores candidates, verifies profiles, and classifies them into hiring tiers with generated interview questions.

---

## 📋 Table of Contents

- 🎥 Demo Video  
- ✨ Features  
- 🛠 Tech Stack  
- 🚀 Setup Instructions   
- 📄 API Documentation  
- 🧠 AI Pipeline  
- 🏗 Architecture Overview  
- 🧪 Testing  
- 🚧 Limitations & Future Improvements  
- 🤖 AI Usage  
- 👨‍💻 Author  

---

## 🎥 Demo Video

🔗 https://youtu.be/nU0GAUxjZJc 

---

## ✨ Features

### 🔧 Backend (FastAPI)

- Resume parsing & evaluation
- Job Description matching
- Multi-dimensional scoring system
- Candidate verification (GitHub / LinkedIn)
- Tier classification (A / B / C)
- AI-generated interview questions
- Batch processing for large datasets
- REST API endpoints

---

## 🛠 Tech Stack

| Layer       | Technology |
|------------|-----------|
| Backend     | FastAPI |
| Language    | Python |
| AI Models   | Google Generative AI / LLM |
| Data Format | JSON |
| Server      | Uvicorn |

---

## 🚀 Setup Instructions

### 1️⃣ Clone Repository

```bash
git clone https://github.com/shubhamkrbxr22/shubham-kumar.git
cd shubham-kumar
```

---

### 2️⃣ Create Virtual Environment

```bash
python -m venv venv
```

Activate the environment:

**Windows**

```bash
venv\Scripts\activate
```

**Mac/Linux**

```bash
source venv/bin/activate
```

---

### 3️⃣ Install Dependencies

```bash
pip install fastapi uvicorn python-dotenv google-generativeai
```

---

### 4️⃣ Configure Environment Variables

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_api_key_here
```

### 5️⃣ Run the Server

```bash
python -m uvicorn src.api:app --reload
```

> Make sure your FastAPI app instance is defined as:
>
> ```python
> app = FastAPI()
> ```

---

### 6️⃣ Access API Documentation

Open in browser:

```
http://127.0.0.1:8000/docs
```

---

### 7️⃣ Test the API

* Use Swagger UI (`/docs`)
* Or tools like Postman
* Test endpoints like `/evaluate`

## 📄 API Documentation

### 🔹 1. Evaluate Candidate

**POST** `/evaluate`

**Request Body:**

```json
{
  "job_description": "string",
  "resume": "string",
  "github_url": "optional",
  "linkedin_url": "optional"
}
```

**Response:**

```json
{
  "score": 85,
  "tier": "A",
  "summary": "Strong backend experience with distributed systems",
  "questions": ["Explain Kafka architecture", "How does Kubernetes scaling work?"]
}
```

---

### 🔹 2. Batch Evaluation

**POST** `/batch-evaluate`

**Request Body:**

```json
{
  "candidates": [
    {
      "resume": "string",
      "job_description": "string"
    }
  ]
}
```

**Response:**

```json
{
  "results": [...]
}
```



## 🧠 AI Pipeline

1. Resume Parsing
2. Job Description Analysis
3. Semantic Matching using LLM
4. Multi-Dimensional Scoring:

   * Exact Match
   * Semantic Similarity
   * Achievement Impact
   * Ownership Depth
5. Candidate Verification (GitHub / LinkedIn)
6. Tier Classification (A / B / C)
7. AI-based Interview Question Generation



## 🏗 Architecture Overview

Frontend (UI)
↓
FastAPI Backend
↓
AI Model (Google Generative AI)
↓
Scoring Engine + Tiering Logic
↓
Response (Score + Tier + Questions)

* Backend handles all logic and API calls
* AI model is used for semantic understanding
* System is scalable and can handle batch processing
  <img width="1536" height="1024" alt="dc" src="https://github.com/user-attachments/assets/dee5fe85-b5f0-473b-af63-10e077f3a1e9" />


## 🧪 Testing

* Tested using Postman for API endpoints
* Sample resumes and job descriptions used
* Verified scoring consistency across multiple runs
* Edge cases tested (empty resume, invalid input)


## 🚧 Limitations & Future Improvements

### Limitations:

* AI responses may vary slightly
* No real-time GitHub/LinkedIn validation
* Requires API key for AI model

### Future Improvements:

* Add authentication system
* Improve scoring accuracy with fine-tuning
* Add UI dashboard with analytics
* Real-time API integrations


## 🤖 AI Usage

* Used Google Generative AI for:

  * Resume understanding
  * Semantic matching
  * Question generation

* AI is used as a decision-support system, not a final authority

## 👨‍💻 Author

**Shubham Kumar**

* GitHub: https://github.com/shubhamkrbxr22


