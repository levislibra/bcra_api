BCRA_API Project

Overview

BCRA_API is a comprehensive FastAPI project designed to handle and process large datasets related to financial and debtor information. It leverages a PostgreSQL database to manage and store data efficiently, enabling users to upload, process, and query substantial amounts of financial data through a RESTful API.

Project Structure

The project is organized into multiple components to ensure clarity and modularity:

	•	Docker Compose Configuration: Defines services for the application and database.
	•	Dockerfile: Sets up the Python environment for the FastAPI application.
	•	Requirements: Lists all dependencies needed for the application.
	•	Main Application (main.py): Contains the main logic and API endpoint definitions.
	•	Database Configuration (database.py): Handles the database connection and setup.
	•	Models (models.py): Defines the database models used for storing data.

Prerequisites

Ensure that you have the following installed on your system:

	•	Docker
	•	Docker Compose
	•	Python 3.9 (optional if running locally without Docker)

Getting Started

Follow these steps to set up and run the project:

1. Clone the Repository

git clone https://github.com/your-repository/bcra_api.git
cd bcra_api

2. Build and Run with Docker Compose

Make sure Docker is running, and then execute:

docker-compose up --build

3. Run the Project

To run the project in detached mode:

docker-compose up -d

4. Access the Database

To access the PostgreSQL database:

docker exec -it postgres_db psql -U user_bcra -d bcra_deudores

5. Create Tables Manually (Optional)

If tables are not generated automatically, create them manually:

Create deudores Table

CREATE TABLE deudores (
    id SERIAL PRIMARY KEY,
    codigo_entidad VARCHAR(5) NOT NULL,
    fecha_informacion VARCHAR(6) NOT NULL,
    tipo_identificacion VARCHAR(2) NOT NULL,
    numero_identificacion VARCHAR(11) NOT NULL,
    actividad VARCHAR(3) NOT NULL,
    situacion INTEGER NOT NULL,
    prestamos_total_garantias NUMERIC(12, 1),
    sin_uso NUMERIC(12, 1),
    garantias_otorgadas NUMERIC(12, 1),
    otros_conceptos NUMERIC(12, 1),
    garantias_preferidas_a NUMERIC(12, 1),
    garantias_preferidas_b NUMERIC(12, 1),
    sin_garantias_preferidas NUMERIC(12, 1),
    contragarantias_preferidas_a NUMERIC(12, 1),
    contragarantias_preferidas_b NUMERIC(12, 1),
    sin_contragarantias_preferidas NUMERIC(12, 1),
    previsiones NUMERIC(12, 1),
    deuda_cubierta INTEGER NOT NULL,
    proceso_judicial_revision INTEGER NOT NULL,
    refinanciaciones INTEGER NOT NULL,
    recategorizacion_obligatoria INTEGER NOT NULL,
    situacion_juridica INTEGER NOT NULL,
    irrecuperables_disposicion_tecnica INTEGER NOT NULL,
    dias_atraso INTEGER NOT NULL,
    nombre_entidad VARCHAR(254) NOT NULL
);

Create entidades Table

CREATE TABLE entidades (
    id SERIAL PRIMARY KEY,
    codigo_entidad VARCHAR(5) UNIQUE NOT NULL,
    nombre_entidad VARCHAR(70) NOT NULL
);

Create padrones Table

CREATE TABLE padrones (
    id SERIAL PRIMARY KEY,
    identificacion VARCHAR(11) NOT NULL,
    denominacion VARCHAR(160) NOT NULL,
    actividad VARCHAR(6),
    marca_baja CHAR(1),
    cuit_reemplazo VARCHAR(11),
    fallecimiento CHAR(1)
);

6. Environment Details

	•	DATABASE_URL: Connection string set in docker-compose.yml.

7. API Endpoints

	•	Upload Endpoint: Upload and process data files.
	•	Debtor Information Endpoint: Query debtor data.
	•	Padron Processing Endpoint: Process and store padron data.

8. Contact

Librasoft SAS
Email: levislibra@libra-soft.com

If you need a downloadable version or further adjustments, let me know!
