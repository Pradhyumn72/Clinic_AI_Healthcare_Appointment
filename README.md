# Healthcare Appointment & Follow-up Manager

A Django-based healthcare appointment management platform connecting
patients, doctors, and administrators through role-based portals.

## 1. Project Overview

The system is designed for appointment booking plus pre-visit symptom
collection, AI-assisted summaries, doctor consultation notes, and
post-visit follow-up information.

### Patient workflow

1.  Register and log in.
2.  Search doctors by specialization.
3.  View available slots.
4.  Select a slot and submit symptoms.
5.  Confirm the appointment.
6.  View appointment and consultation information.

### Doctor workflow

1.  Log in.
2.  View upcoming appointments.
3.  Review pre-visit symptom information.
4.  Enter clinical notes and prescription information.
5.  Generate a patient-friendly post-visit summary.

### Admin workflow

Administrators manage doctors, schedules, and leave through Django
Admin.

## 2. Technology Stack

  Layer            Technology
  ---------------- ---------------------------------------------
  Backend          Django
  Frontend         HTML, CSS, Vanilla JavaScript
  Database         SQLite
  ORM              Django ORM
  AI               Anthropic Claude API / Mock LLM
  Authentication   Django Authentication + Custom User
  Dynamic API      Django JSON endpoint + JavaScript `fetch()`

## 3. Project Structure

``` text
Clinic_AI_Healthcare_Appointment/
├── accounts/
├── doctors/
├── appointments/
├── consultations/
├── notifications_app/
├── clinic_project/
├── templates/
├── static/
├── manage.py
├── requirements.txt
└── db.sqlite3
```

### Application responsibilities

**accounts** --- Custom User, authentication, registration, roles,
dashboard routing, and access control.

**doctors** --- Doctor profiles, specialization, working hours/days,
slot duration, availability, and leave.

**appointments** --- Appointment records, availability, booking, slot
holding, cancellation, and concurrent-booking protection.

**consultations** --- Symptoms, AI pre-visit summaries, clinical notes,
prescriptions, and AI post-visit summaries.

**notifications_app** --- Notification/external-integration layer.

## 4. Database Design

``` text
User
  │
  ├── 1:1 ── DoctorProfile
  │              ├── 1:N ── Leave
  │              └── 1:N ── Appointment
  │                              ├── 1:1 ── SymptomForm
  │                              └── 1:1 ── PostVisitNote
  │
  └── 1:N ── Appointment
```

### User

Custom Django user extending `AbstractUser`.

Important fields: - `username` - `email` - `role` - `phone_number` -
`date_of_birth`

Roles: - `patient` - `doctor` - `admin`

### DoctorProfile

Stores: - Associated user - Specialization - Working hours - Working
days - Slot duration - Biography - Active/inactive state

### Leave

Stores doctor leave dates and prevents duplicate leave records for the
same doctor/date.

### Appointment

Central scheduling entity containing: - Patient - Doctor - Date -
Start/end time - Status - Hold expiration - Calendar event identifiers -
Creation/update timestamps

Appointment statuses:

``` text
held
confirmed
cancelled
completed
leave_cancelled
```

### SymptomForm

Stores symptoms and AI output: - Symptoms - Urgency - Chief complaint -
Suggested questions - LLM status - Raw LLM response

### PostVisitNote

Stores: - Clinical notes - Prescription - Medication data - Patient
summary - Follow-up steps - LLM status

## 5. Double-Booking Prevention

Booking is protected at multiple levels.

``` text
Booking Request
      │
      ▼
transaction.atomic()
      │
      ▼
select_for_update()
      │
      ▼
Check active slot
      │
      ├── Already booked → friendly error
      │
      ▼
Create HELD appointment
      │
      ▼
Database uniqueness constraint
      │
      └── Race condition → IntegrityError → friendly error
```

The active-slot uniqueness rule conceptually protects:

``` text
doctor + date + start_time
```

for `held` and `confirmed` appointments.

## 6. Slot Availability API

### Endpoint

``` http
GET /appointments/api/slots/
```

### Parameters

``` text
doctor_id
date
```

Example:

``` http
GET /appointments/api/slots/?doctor_id=2&date=2026-08-25
```

Example response:

``` json
{
  "doctor_id": 2,
  "date": "2026-08-25",
  "slots": ["09:00", "09:30", "10:00", "10:30"]
}
```

Possible errors:

-   `400` --- missing parameters or invalid date
-   `404` --- doctor not found

## 7. Main Routes

  Method     Endpoint                        Purpose
  ---------- ------------------------------- ----------------------
  GET/POST   `/accounts/register/`           Patient registration
  GET        `/accounts/login/`              Login
  POST       `/accounts/logout/`             Logout
  GET        `/accounts/dashboard/`          Role-based dashboard
  GET        `/appointments/api/slots/`      Available slots
  GET        `/appointments/doctors/`        Doctor search
  GET        `/appointments/doctors/<id>/`   Doctor details
  POST       `/appointments/book/`           Hold/book a slot
  GET        `/appointments/mine/`           Patient appointments
  GET        `/appointments/doctor/`         Doctor appointments
  POST       `/appointments/<id>/cancel/`    Cancel appointment

## 8. AI Integration

AI functionality is isolated in:

``` text
consultations/llm_service.py
```

Primary operations:

``` python
generate_pre_visit_summary(symptoms_text)
generate_post_visit_summary(clinical_notes, prescription_text)
```

### Pre-visit prompt

``` text
Analyse these symptoms and return: urgency level (Low / Medium / High),
chief complaint, and three suggested questions for the doctor.
Symptoms: <symptoms>
```

### Post-visit prompt

``` text
Convert these clinical notes into a patient-friendly summary with medication
schedule and follow-up steps: <notes>
```

LLM failures are handled without crashing the appointment/consultation
flow. Mock mode can be used for demonstrations without live credentials.

## 9. Code Architecture

``` text
Browser
   │
   ▼
Django Views
   │
   ├───────────────┐
   ▼               ▼
Models          Services
                   │
             ┌─────┴─────┐
             ▼           ▼
          Booking       LLM
           Logic       Service
             │
             ▼
          SQLite
```

`appointments/services.py` keeps concurrency-sensitive booking logic
separate from views.

`consultations/llm_service.py` isolates AI-specific behavior.

## 10. Setup

### Prerequisites

-   Python 3.x
-   pip
-   Git

### Clone

``` bash
git clone https://github.com/Pradhyumn72/Clinic_AI_Healthcare_Appointment.git
cd Clinic_AI_Healthcare_Appointment
```

### Virtual environment

Windows:

``` bash
python -m venv venv
venv\Scripts\activate
```

macOS/Linux:

``` bash
python3 -m venv venv
source venv/bin/activate
```

### Install dependencies

``` bash
pip install -r requirements.txt
```

### Environment configuration

Create `.env` from `.env.example`.

For demo mode, use:

``` text
MOCK_LLM=True
```

Never commit API keys or other secrets.

### Migrate

``` bash
python manage.py migrate
```

### Run

``` bash
python manage.py runserver
```

Open:

``` text
http://127.0.0.1:8000/
```

## 11. Admin Setup

Create an administrator:

``` bash
python manage.py createsuperuser
```

Then open:

``` text
http://127.0.0.1:8000/admin/
```

## 12. Demo Flow

1.  Create/login as a patient.
2.  Search for a doctor.
3.  Select an available date and slot.
4.  Submit symptoms.
5.  Generate the pre-visit AI/mock-AI summary.
6.  Confirm the appointment.
7.  Login as a doctor.
8.  Open the appointment.
9.  Enter clinical notes and prescription.
10. Generate the post-visit summary.

## 13. Reliability and Security

The architecture emphasizes: - Role-based access control - Server-side
validation - Transactional booking - Row locking - Database-level
booking constraints - Graceful LLM failure handling - Environment
variables for secrets - Timezone-aware Django configuration - Separation
of business logic from views

## 14. Implementation Status

The reviewed repository contains the following core functionality:

### Implemented / present

-   Custom User and roles
-   DoctorProfile
-   Doctor leave
-   Appointment model
-   Slot availability
-   Slot holding
-   Double-booking protection
-   SymptomForm
-   PostVisitNote
-   LLM / Mock LLM service
-   Dynamic slot JSON API
-   Modular Django app structure

### Verify before claiming as complete

The project specification also calls for EmailLog/retry infrastructure,
medication reminders, Google Calendar OAuth/event management, and
background notification jobs. These should only be described as fully
implemented if the corresponding code is present in the final submitted
repository.

## 15. Evaluation Highlights

### Database Schema Design

-   Clear entity relationships
-   Foreign-key and one-to-one relationships
-   Appointment lifecycle
-   Conditional uniqueness for active slots
-   JSON storage for semi-structured AI data

### API Design

-   Dedicated JSON endpoint for dynamic slot availability
-   Parameter validation
-   Appropriate HTTP status codes
-   Django routes for application workflows

### Code Structure

-   Modular Django applications
-   Separation of authentication, scheduling, and consultation logic
-   Dedicated booking service layer
-   Dedicated LLM service

### Problem Solving

-   Concurrent booking protection
-   Slot holding
-   Appointment state management
-   Graceful AI failure handling

## 16. Conclusion

The project follows a clear appointment lifecycle:

``` text
Patient
   ↓
Doctor Search
   ↓
Slot Availability
   ↓
Slot Hold
   ↓
Symptoms
   ↓
AI Pre-Visit Summary
   ↓
Confirmed Appointment
   ↓
Doctor Consultation
   ↓
Clinical Notes + Prescription
   ↓
AI Post-Visit Summary
```

The architecture combines Django's modular structure with database-level
scheduling safeguards and isolated AI services. The strongest design
feature is the layered double-booking protection using transactions,
locking, and database constraints.
