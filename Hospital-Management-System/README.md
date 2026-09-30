# Hospital Management System

A comprehensive, modular, and secure Hospital Management System (HMS) built with Flask. This enterprise-grade application is designed to streamline hospital operations, from patient management and appointments to billing, reporting, and clinical decision support.

## Features

The system is organized into several key modules:

-   **Patient Management**: Register, search, and manage patient profiles and medical histories.
-   **Doctor & Staff Management**: Maintain profiles for doctors, nurses, and other hospital staff.
-   **Appointment Scheduling**: Book, view, and manage patient appointments with doctors.
-   **Electronic Medical Records (EMR)**: A complete EMR system to record patient visits, diagnoses, treatments, and clinical notes.
-   **Billing & Invoicing**: Generate invoices, record payments, and manage financial transactions.
-   **Ward & Bed Management**: Manage hospital buildings, wards, rooms, and bed occupancy.
-   **Human Resources (HR)**: Manage employee profiles, attendance, and leave.
-   **Procurement & Inventory**: Control the hospital's supply chain, from suppliers and products to purchase orders and goods receiving.
-   **Emergency Management**: Track emergency calls and manage the ambulance fleet.
-   **Security & Audit**: A robust module for logging user activity, tracking security events, and managing access control.
-   **System Administration**: Configure hospital information, system settings, and perform maintenance tasks.
-   **AI Clinical Assistant**: A decision-support tool for staff to summarize patient data, draft clinical documents, and search policies.
-   **Reporting Center**: Generate detailed reports (PDF, Excel, CSV) and view interactive dashboards on various hospital metrics.
-   **Patient, Doctor & Nurse Portals**: Dedicated dashboards for different user roles to access relevant information and tasks.

## Technologies

-   **Backend**: Flask (Python)
-   **Database**: PostgreSQL (Production), SQLite (Development)
-   **ORM**: Flask-SQLAlchemy
-   **Migrations**: Flask-Migrate
-   **Authentication**: Flask-Login
-   **Forms & Security**: Flask-WTF (CSRF Protection)
-   **Frontend**: Bootstrap 5, Chart.js, Font Awesome
-   **Deployment**: Docker, Gunicorn, Nginx (recommended)
-   **Reporting**: Pandas, ReportLab, openpyxl

## Production Setup & Deployment

This application is designed to be deployed using Docker for consistency and scalability.

### Prerequisites

-   Docker
-   Docker Compose

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd Hospital-Management-System
    ```

2.  **Create an environment file:**
    Copy the sample environment file and customize it with your own secure values.
    ```bash
    cp .env.sample .env
    ```
    **Important:** Change `SECRET_KEY` and `POSTGRES_PASSWORD` to strong, random values.

3.  **Build and run with Docker Compose:**
    This command will build the Docker images and start the application, database, and other services.
    ```bash
    docker-compose up --build -d
    ```

4.  **Initialize the database and run migrations:**
    The first time you run the application, you need to create the database tables.
    ```bash
    docker-compose exec web flask db init
    docker-compose exec web flask db migrate -m "Initial migration"
    docker-compose exec web flask db upgrade
    ```

5.  **Seed the database with sample data (Optional):**
    To populate the system with demo users, patients, and doctors, run the seed script.
    ```bash
    docker-compose exec web python seed.py
    ```

6.  **Access the application:**
    The application should now be running. Access it at `http://localhost:80` (if using Nginx) or `http://localhost:5000` (if accessing the web service directly).

### Default Login Credentials

-   **Administrator**:
    -   **Username**: `admin`
    -   **Password**: `admin123`
-   **Doctor**:
    -   **Username**: `dr.house@hospital.com`
    -   **Password**: `doctor123`
-   **Patient**:
    -   **Username**: `john.doe@email.com`
    -   **Password**: `patient123`

## Development

For local development without Docker:

1.  Create a Python virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Set up a local PostgreSQL database or use the default SQLite by commenting out the `SQLALCHEMY_DATABASE_URI` in `config.py`.

4.  Run the Flask development server:
    ```bash
    flask run
    ```

## Screenshots

*(This section can be filled with screenshots of the main dashboard, patient profiles, reporting center, etc.)*

---

*This project serves as a comprehensive, enterprise-level example of a Flask web application.*
