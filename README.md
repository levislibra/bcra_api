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

	•	git clone https://github.com/your-repository/bcra_api.git
	•	cd bcra_api

2. Build and Run with Docker Compose

Make sure Docker is running, and then execute:

	•	docker-compose up --build

3. Run the Project

To run the project in detached mode:

	•	docker-compose up -d

4. Access the Database

To access the PostgreSQL database:

	•	docker exec -it postgres_db psql -U user_bcra -d bcra_deudores

5. Create Tables Manually (Optional)

If tables are not generated automatically, create them manually:

Create deudores Table

	•	CREATE TABLE deudores (
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

	•	CREATE TABLE entidades (
			id SERIAL PRIMARY KEY,
			codigo_entidad VARCHAR(5) UNIQUE NOT NULL,
			nombre_entidad VARCHAR(70) NOT NULL
		);

Create padrones Table

	•	CREATE TABLE padrones (
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

8. Add index to improve performance

Here’s a recommended summary of indexes to optimize the database performance for the deudores and padrones tables. These indexes will improve the speed of search queries on key fields.

Indexes for deudores Table

Primary Identifiers
numero_identificacion: Index to quickly locate records by identification number (CUIT, DNI). This is the most critical index for queries where deudores are looked up by their identification.

	•	CREATE INDEX idx_deudores_numero_identificacion ON deudores (numero_identificacion);


Textual Fields for Fuzzy Search
nombre_entidad: Index to enable faster searches by the entity name when looking up by the bank or other textual criteria.

	•	CREATE INDEX idx_deudores_nombre_entidad ON deudores (nombre_entidad);


Composite Index for Filtering and Sorting
(fecha_informacion, numero_identificacion): Composite index to speed up queries that filter by numero_identificacion and order by the latest fecha_informacion.

	•	CREATE INDEX idx_deudores_fecha_informacion_identificacion ON deudores (fecha_informacion, numero_identificacion);



Indexes for padrones Table

Primary Identifiers
identificacion: Essential index for searching by unique identification (CUIT/CUIL). This index ensures that searches by identification will be quick and efficient.

	•	CREATE INDEX idx_padrones_identificacion ON padrones (identificacion);


Textual Fields for Search by Name
denominacion: Index to speed up searches on the denominacion field when querying for names, especially useful for partial or fuzzy matching.

	•	CREATE INDEX idx_padrones_denominacion ON padrones (denominacion);

Additionally, to improve performance for partial and fuzzy text searches on the denominacion field in the padrones table, you can leverage PostgreSQL’s trigram indexing.

Additional Index for padrones Table

Trigram Index for Faster Text Search
Trigram Extension: Install the trigram extension for PostgreSQL if it’s not already enabled. This extension enhances text search capabilities, especially for partial matches and similarity searches.

	•	CREATE EXTENSION IF NOT EXISTS pg_trgm;


Trigram Index on denominacion: Create a trigram-based GIN index on denominacion to optimize queries that search for names with partial matches or similar text patterns. This index is particularly useful if you are performing ILIKE or similarity searches.

	•	CREATE INDEX idx_padrones_denominacion_trgm ON padrones USING gin (denominacion gin_trgm_ops);


By including this trigram index, queries on denominacion in the padrones table will be significantly faster for searches involving partial or approximate matching, making it ideal for large datasets where text search efficiency is crucial.

9. Contact

Librasoft SAS
Email: levislibra@libra-soft.com

If you need a downloadable version or further adjustments, let me know!
