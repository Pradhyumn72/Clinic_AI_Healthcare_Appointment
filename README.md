# 🏥 Healthcare Appointment & Follow-up Manager

> **Django • SQLite • Role-Based Access • Concurrency-Safe Booking •
> AI-Assisted Consultation**

A Django-based healthcare appointment platform designed around the
complete appointment lifecycle --- from doctor discovery and slot
booking to pre-visit symptom collection and AI-assisted post-visit
follow-up.

The project is intentionally designed beyond a basic CRUD booking
application. Its key engineering focus is **reliable appointment
scheduling under concurrent requests**, clean separation of domain
responsibilities, and an isolated LLM service for consultation
assistance.

------------------------------------------------------------------------

## ⭐ Why This Project Stands Out

### 1. Concurrency-safe appointment booking

A normal availability check is not enough when two patients attempt to
book the same slot at nearly the same time.

This project uses multiple protection layers:

``` text
Patient Request
      │
      ▼
transaction.atomic()
      │
      ▼
select_for_update()
      │
      ▼
Check active appointment
      │
      ├── Already booked → Friendly error
      │
      ▼
Create HELD appointment
      │
      ▼
Database-level uniqueness constraint
      │
      └── Race condition → IntegrityError → Friendly error
```

This combines **application-level synchronization** with a
**database-level consistency guarantee**.

------------------------------------------------------------------------

### 2. Explicit appointment lifecycle

Appointments are modeled as states instead of being treated as a single
database row:

``` text
HELD
  │
  ▼
CONFIRMED
  │
  ▼
COMPLETED
```

with cancellation states such as:

``` text
CANCELLED
LEAVE_CANCELLED
```

Temporary slot holding is represented using:

``` text
hold_expires_at
```

------------------------------------------------------------------------

### 3. AI is isolated from the core application

AI functionality is kept inside:

``` text
consultations/llm_service.py
```

The application uses dedicated service functions for:

``` python
generate_pre_visit_summary()
generate_post_visit_summary()
```

The design also supports a **Mock LLM** workflow so the project can be
demonstrated without requiring live external API credentials.

------------------------------------------------------------------------

## 🎯 Project Objective

The system addresses the workflow around a healthcare appointment rather
than only appointment creation.

### Patient

``` text
Register
   ↓
Login
   ↓
Search Doctors
   ↓
View Available Slots
   ↓
Hold Slot
   ↓
Submit Symptoms
   ↓
AI Pre-Visit Information
   ↓
Confirm Appointment
   ↓
View Consultation Information
```

### Doctor

``` text
Login
   ↓
View Appointments
   ↓
Review Patient Symptoms
   ↓
Enter Clinical Notes
   ↓
Enter Prescription
   ↓
AI-Assisted Post-Visit Summary
```

### Admin

Administrative functionality is provided through Django's
authentication/admin architecture for managing system data and
doctor-related information where configured.

------------------------------------------------------------------------

# 🏗️ System Architecture

``` text
                    ┌──────────────────────┐
                    │        Patient       │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     Django Views     │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌───────────┐   ┌──────────────┐  ┌──────────────┐
        │ Accounts  │   │ Appointments │  │ Consultations│
        └───────────┘   └──────┬───────┘  └──────┬───────┘
                                │                 │
                                ▼                 ▼
                         ┌────────────┐    ┌──────────────┐
                         │  Booking   │    │ LLM Service  │
                         │  Service   │    └──────┬───────┘
                         └──────┬─────┘           │
                                │                 ▼
                                ▼          ┌──────────────┐
                           ┌─────────┐     │ Claude / Mock │
                           │ SQLite  │     │     LLM       │
                           └─────────┘     └──────────────┘
```

The application uses Django's server-rendered architecture with HTML
templates and JavaScript `fetch()` for asynchronous slot availability.

------------------------------------------------------------------------

# 🧩 Project Structure

``` text
Clinic_AI_Healthcare_Appointment/
│
├── accounts/
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── decorators.py
│   ├── urls.py
│   └── admin.py
│
├── doctors/
│   ├── models.py
│   ├── views.py
│   └── admin.py
│
├── appointments/
│   ├── models.py
│   ├── views.py
│   ├── services.py
│   └── urls.py
│
├── consultations/
│   ├── models.py
│   ├── views.py
│   └── llm_service.py
│
├── notifications_app/
│
├── clinic_project/
│   ├── settings.py
│   └── urls.py
│
├── templates/
├── static/
├── manage.py
├── requirements.txt
└── db.sqlite3
```

## Application responsibilities

  -----------------------------------------------------------------------
  App                                 Responsibility
  ----------------------------------- -----------------------------------
  `accounts`                          Custom User, authentication, roles,
                                      registration, dashboard routing and
                                      access control

  `doctors`                           Doctor profiles, specialization,
                                      working schedule, slot duration and
                                      leave

  `appointments`                      Availability, booking, slot
                                      holding, cancellation and
                                      concurrency protection

  `consultations`                     Symptoms, AI pre-visit summary,
                                      clinical notes, prescriptions and
                                      post-visit summary

  `notifications_app`                 Notification/integration layer
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 🗄️ Database Schema

The core database relationship is:

``` text
User
 │
 ├── 1:1 ── DoctorProfile
 │              │
 │              ├── 1:N ── Leave
 │              │
 │              └── 1:N ── Appointment
 │                              │
 │                              ├── 1:1 ── SymptomForm
 │                              │
 │                              └── 1:1 ── PostVisitNote
 │
 └── 1:N ── Appointment
```

## Core entities

### User

Custom Django user containing:

-   `username`
-   `email`
-   `role`
-   `phone_number`
-   `date_of_birth`

Supported roles:

``` text
patient
doctor
admin
```

### DoctorProfile

Stores:

-   User relationship
-   Specialization
-   Working hours
-   Working days
-   Slot duration
-   Biography
-   Active/inactive state

### Leave

Stores:

-   Doctor
-   Leave date
-   Reason
-   Creation timestamp

The doctor/date combination is unique to prevent duplicate leave
records.

### Appointment

Stores:

-   Patient
-   Doctor
-   Date
-   Start/end time
-   Appointment status
-   Hold expiration
-   Calendar event identifiers
-   Creation/update timestamps

### SymptomForm

Stores:

-   Patient symptoms
-   Urgency level
-   Chief complaint
-   AI-generated suggested questions
-   LLM status
-   Raw LLM response

### PostVisitNote

Stores:

-   Clinical notes
-   Prescription
-   Medication data
-   AI-generated patient summary
-   Follow-up steps
-   LLM status

------------------------------------------------------------------------

# 🔐 Double-Booking Protection

This is one of the core engineering decisions in the project.

## The problem

Suppose two patients request:

``` text
Doctor: Dr. X
Date: 2026-08-25
Time: 10:00
```

at almost the same time.

A simple:

``` python
if slot_is_available:
    create_appointment()
```

is not sufficient because both requests may observe the slot before
either transaction commits.

## The solution

The booking flow uses:

``` python
transaction.atomic()
```

and:

``` python
select_for_update()
```

together with a database constraint for active appointments.

Conceptually:

``` text
doctor + date + start_time
```

must remain unique while the appointment is:

``` text
held
confirmed
```

If a race condition reaches the database constraint, `IntegrityError` is
handled and converted into a user-friendly slot-unavailable response.

### Why this matters

This provides protection at multiple levels:

``` text
Application validation
        +
Transaction
        +
Row locking
        +
Database constraint
```

------------------------------------------------------------------------

# ⏱️ Appointment & Slot-Hold Flow

``` text
GET /appointments/api/slots/
          │
          ▼
Patient selects slot
          │
          ▼
POST /appointments/book/
          │
          ▼
hold_slot()
          │
          ├── status = HELD
          └── hold_expires_at = set
          │
          ▼
Patient submits symptoms
          │
          ▼
LLM generates pre-visit information
          │
          ▼
Appointment → CONFIRMED
          │
          ▼
Doctor consultation
```

The hold mechanism prevents a selected slot from being treated as
permanently available while the patient completes the booking workflow.

------------------------------------------------------------------------

# 🌐 API Design

## Available Slots API

### Endpoint

``` http
GET /appointments/api/slots/
```

### Parameters

``` text
doctor_id
date
```

### Example

``` http
GET /appointments/api/slots/?doctor_id=2&date=2026-08-25
```

### Response

``` json
{
  "doctor_id": 2,
  "date": "2026-08-25",
  "slots": [
    "09:00",
    "09:30",
    "10:00",
    "10:30"
  ]
}
```

The endpoint validates the doctor/date, calculates working slots,
removes occupied/unavailable slots, and returns the remaining slots as
JSON.

### Error handling

  Condition                         HTTP Response
  ------------------------------ ------- ---------------------------
  Missing `doctor_id` / `date`     `400` Required query parameters
  Invalid doctor                   `404` Doctor not found
  Invalid date                     `400` Invalid date format

## Main application routes

  Method     Endpoint                        Purpose
  ---------- ------------------------------- -----------------------------
  GET/POST   `/accounts/register/`           Patient registration
  GET        `/accounts/login/`              Login
  POST       `/accounts/logout/`             Logout
  GET        `/accounts/dashboard/`          Role-based dashboard
  GET        `/appointments/api/slots/`      Available appointment slots
  GET        `/appointments/doctors/`        Doctor search
  GET        `/appointments/doctors/<id>/`   Doctor details and slots
  POST       `/appointments/book/`           Hold/book appointment
  GET        `/appointments/mine/`           Patient appointments
  GET        `/appointments/doctor/`         Doctor appointments
  POST       `/appointments/<id>/cancel/`    Cancel appointment

------------------------------------------------------------------------

# 🤖 AI Architecture

AI functionality is isolated inside:

``` text
consultations/llm_service.py
```

## Pre-visit AI

``` text
Patient Symptoms
       │
       ▼
generate_pre_visit_summary()
       │
       ▼
Claude API / Mock LLM
       │
       ▼
Structured information
       │
       ▼
SymptomForm
```

The pre-visit workflow is designed to produce:

-   Urgency level
-   Chief complaint
-   Suggested questions for the doctor

## Post-visit AI

``` text
Clinical Notes + Prescription
       │
       ▼
generate_post_visit_summary()
       │
       ▼
Claude API / Mock LLM
       │
       ▼
Patient Summary
Medication Information
Follow-up Steps
```

## AI reliability

LLM processing has explicit status tracking:

``` text
pending
success
failed
```

The architecture treats AI failure as a recoverable application
condition rather than allowing an external AI dependency to crash the
appointment workflow.

------------------------------------------------------------------------

# 🧠 Key Design Decisions

  -----------------------------------------------------------------------
  Decision                            Reason
  ----------------------------------- -----------------------------------
  **Django + ORM**                    Provides authentication, ORM,
                                      routing, forms and admin while
                                      keeping the healthcare-specific
                                      logic modular.

  **SQLite**                          Suitable for the development/demo
                                      environment specified for the
                                      project.

  **Separate Django apps**            Reduces coupling between
                                      authentication, doctors,
                                      appointments and consultations.

  **Service layer**                   Keeps concurrency-sensitive booking
                                      logic outside views and makes it
                                      reusable/testable.

  **Database constraint**             Provides a final consistency
                                      guarantee beyond application-level
                                      availability checks.

  **JSONField**                       Suitable for semi-structured AI
                                      output such as suggested questions
                                      and medication data.

  **Mock LLM**                        Keeps the AI workflow demoable
                                      without requiring live external
                                      credentials.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 📋 Requirement → Implementation

  -----------------------------------------------------------------------
  Requirement                         Implementation
  ----------------------------------- -----------------------------------
  Role-based authentication           Custom User + role-aware access
                                      control

  Doctor profiles                     `DoctorProfile`

  Doctor leave                        `Leave`

  Appointment scheduling              `Appointment` + booking service

  Temporary slot holding              `HELD` status + `hold_expires_at`

  Double-booking prevention           Transaction + row locking + DB
                                      constraint

  Dynamic slot availability           `/appointments/api/slots/`

  Pre-visit AI                        `SymptomForm` + LLM service

  Post-visit AI                       `PostVisitNote` + LLM service

  LLM failure tracking                `llm_status`

  Modular architecture                Separate Django apps

  Notification/integration layer      `notifications_app`
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 🔎 Code Walkthrough

A typical booking request flows through:

``` text
Browser
   ↓
appointments/views.py
   ↓
appointments/services.py
   ↓
Appointment validation
   ↓
transaction.atomic()
   ↓
select_for_update()
   ↓
Database constraint
   ↓
Appointment
```

The most important implementation areas are therefore easy to locate:

  File                             What to inspect
  -------------------------------- ------------------------------------
  `appointments/models.py`         Appointment schema and constraints
  `appointments/views.py`          HTTP request handling
  `appointments/services.py`       Booking/business logic
  `appointments/urls.py`           Appointment routes
  `doctors/models.py`              Doctor schedule/slot logic
  `consultations/models.py`        Symptom and post-visit data
  `consultations/llm_service.py`   AI integration
  `accounts/models.py`             Custom User and roles
  `accounts/decorators.py`         Role/access control

------------------------------------------------------------------------

# 🛠️ Setup

## Prerequisites

-   Python 3.x
-   pip
-   Git

## Clone

``` bash
git clone https://github.com/Pradhyumn72/Clinic_AI_Healthcare_Appointment.git
cd Clinic_AI_Healthcare_Appointment
```

## Create virtual environment

### macOS / Linux

``` bash
python3 -m venv venv
source venv/bin/activate
```

### Windows

``` bash
python -m venv venv
venv\Scripts\activate
```

## Install dependencies

``` bash
pip install -r requirements.txt
```

## Configure environment variables

Create `.env` based on:

``` text
.env.example
```

For demonstration without a live LLM credential:

``` text
MOCK_LLM=True
```

> Never commit API keys, credentials, or `.env` secrets to GitHub.

## Database migration

``` bash
python manage.py migrate
```

## Create admin user

``` bash
python manage.py createsuperuser
```

## Start server

``` bash
python manage.py runserver
```

Open:

``` text
http://127.0.0.1:8000/
```

Admin:

``` text
http://127.0.0.1:8000/admin/
```

------------------------------------------------------------------------

# 🧪 Suggested Demo Flow

For a quick technical demonstration:

``` text
1. Patient registration
        ↓
2. Doctor search
        ↓
3. Slot availability API
        ↓
4. Slot selection
        ↓
5. Temporary hold
        ↓
6. Symptom submission
        ↓
7. AI/mock-AI pre-visit summary
        ↓
8. Appointment confirmation
        ↓
9. Doctor login
        ↓
10. Clinical notes + prescription
        ↓
11. AI/mock-AI post-visit summary
```

### Best technical demonstration

If presenting the project to an interviewer, demonstrate the **same-slot
concurrency scenario** as a technical highlight.

Explain:

> "I did not rely only on checking whether a slot was available. Because
> two requests can arrive concurrently, I used transactional locking and
> a database constraint as a final consistency guarantee."

------------------------------------------------------------------------

# 📊 Implementation Status

This section intentionally distinguishes implemented functionality from
functionality that should not be claimed as complete unless the
corresponding code exists in the final repository.

### Implemented / present

-   Custom User / roles
-   DoctorProfile
-   Leave model
-   Appointment model
-   Double-booking protection
-   Slot holding
-   SymptomForm
-   PostVisitNote
-   LLM / Mock LLM service
-   Dynamic slot JSON API
-   Modular Django architecture

### Verify before claiming as complete

The project requirements also call for integration areas including:

-   EmailLog / email retry infrastructure
-   MedicationReminder
-   Google Calendar OAuth/event persistence
-   Background notification processing

These should be described as **complete only when the corresponding
implementation is present and working in the final GitHub repository**.

------------------------------------------------------------------------

# 🔒 Reliability & Security Considerations

The project architecture emphasizes:

-   Role-based access control
-   Server-side validation
-   Transactional booking
-   Row locking
-   Database-level appointment constraints
-   Graceful LLM failure handling
-   Environment variables for secrets
-   Timezone-aware Django configuration
-   Separation of business logic from views

For a healthcare application, AI-generated information should be treated
as **assistive information and reviewed by the appropriate healthcare
professional**, not as an autonomous medical decision.

------------------------------------------------------------------------

# 📸 Screenshots / Demo

Add selected screenshots here when available:

``` text
docs/
└── screenshots/
    ├── patient-dashboard.png
    ├── doctor-search.png
    ├── slot-selection.png
    ├── previsit-summary.png
    ├── doctor-consultation.png
    └── postvisit-summary.png
```

Recommended README screenshots:

1.  Doctor search
2.  Available slot selection
3.  Pre-visit AI summary
4.  Doctor consultation
5.  Post-visit summary

A short 60--90 second demo video showing the complete patient → doctor
workflow can also be linked here.

------------------------------------------------------------------------

# 🚀 Future Improvements

Potential production-oriented improvements include:

-   PostgreSQL for production-scale relational storage
-   Redis/Celery for asynchronous jobs
-   Complete Google Calendar OAuth/event workflow
-   Email retry queues
-   Medication reminder scheduling
-   Audit logging for clinical records
-   Automated tests for concurrent booking
-   CI/CD pipeline
-   Dockerized deployment
-   Structured logging and monitoring

These are improvement directions, not claims about the current
implementation.

------------------------------------------------------------------------

# 📚 Technical Documentation

Detailed technical documentation covering the database schema, API
design, code structure, concurrency handling, AI architecture, design
rationale, and implementation boundaries is available in:

``` text
docs/Healthcare_Appointment_Submission_Documentation_AI_Reviewer_Optimized.pdf
```

------------------------------------------------------------------------

# 🏆 Technical Highlights

### Database

-   Relational healthcare workflow
-   Foreign-key and OneToOne relationships
-   Explicit appointment states
-   Conditional uniqueness for active slots
-   JSON storage for semi-structured AI data

### API

-   Dedicated dynamic slot availability endpoint
-   Query parameter validation
-   JSON responses
-   Explicit error handling

### Backend

-   Modular Django applications
-   Service-layer business logic
-   Role-based access control
-   Transaction-safe booking

### AI

-   Isolated LLM service
-   Pre-visit summary generation
-   Post-visit patient-friendly summary
-   Mock LLM support
-   LLM status tracking

### Reliability

-   Concurrent booking protection
-   Database-level consistency
-   Slot holding
-   Graceful AI failure handling

------------------------------------------------------------------------

# 👨‍💻 Project Positioning

This project should be understood as:

> **A Django healthcare appointment platform that combines role-based
> workflows and AI-assisted consultations with concurrency-safe
> appointment scheduling and database-level protection against
> double-booking.**

The core engineering idea is not simply:

``` text
"Book an appointment"
```

It is:

``` text
"Book the correct appointment reliably,
even when multiple requests compete for the same slot,
while integrating AI assistance without coupling the core workflow to the AI provider."
```

------------------------------------------------------------------------

## License

Add the project's applicable license here before public distribution.
