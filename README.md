# ai-assisted-exam-generator
Thesis 


AWEGen: AI-Assisted Written Exam Generator
Overview
AWEGen is an AI-powered exam generation system designed specifically for Pambayang Dalubhasaan ng Marilao (PDM). It automates the creation of written examinations using hybrid NLP algorithms, helping teachers save time and ensure consistent, high-quality assessments.

Features
Core Functionality
AI-Powered Question Generation: Automatically generates multiple question types (Multiple Choice, True/False, Fill in the Blank, Matching)
Bloom's Taxonomy Integration: Classifies questions according to cognitive levels
Table of Specification (TOS): Automatically generates TOS for balanced assessments
Question Bank Management: Maintains a repository of questions to prevent repetition
Multi-Format Export: Export exams to PDF and Word formats
Approval Workflow: Multi-level approval process for exam validation
Role-Based Access: Different interfaces for Teachers, Department Heads, and Administrators
Technical Features
Hybrid NLP Algorithms: Combines TF-IDF, rule-based NLP, and transformer models
Content Processing: Extracts key concepts from uploaded learning materials
Validation System: Allows teachers to review and edit AI-generated questions
Notification System: Real-time updates for approval status and comments
Reporting: Comprehensive exam performance reports
Technology Stack
Backend
Framework: Flask (Python)
Database: PostgreSQL with SQLAlchemy ORM
Authentication: JWT tokens
NLP Libraries: NLTK, spaCy, Transformers
Task Queue: Celery with Redis
Document Processing: python-docx, PyPDF2, python-pptx
Export: ReportLab (PDF), python-docx (Word)
Frontend
Framework: React 18
Build Tool: Vite
Styling: Tailwind CSS
State Management: React Context API
HTTP Client: Axios
Routing: React Router
Deployment
Containerization: Docker
Orchestration: Docker Compose
Web Server: Gunicorn (backend), Nginx (frontend)
Database: PostgreSQL
Cache: Redis
Installation
Prerequisites
Python 3.11+
Node.js 18+
PostgreSQL 15+
Redis 7+
Local Development Setup
Clone the repository
git clone https://github.com/jomari-wq/ai-assisted-exam-generator awegen-exam-generator



