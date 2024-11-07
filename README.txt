# BCRA_API Project

## Overview
**BCRA_API** is a comprehensive FastAPI project designed to handle and process large datasets related to financial and debtor information. It leverages a PostgreSQL database to manage and store data efficiently, enabling users to upload, process, and query substantial amounts of financial data through a RESTful API.

## Project Structure
The project is organized into multiple components to ensure clarity and modularity:

- **Docker Compose Configuration**: Defines services for the application and database.
- **Dockerfile**: Sets up the Python environment for the FastAPI application.
- **Requirements**: Lists all dependencies needed for the application.
- **Main Application (main.py)**: Contains the main logic and API endpoint definitions.
- **Database Configuration (database.py)**: Handles the database connection and setup.
- **Models (models.py)**: Defines the database models used for storing data.

## Prerequisites
Ensure that you have the following installed on your system:
- Docker
- Docker Compose
- Python 3.9 (optional if running locally without Docker)

## Getting Started
Follow these steps to set up and run the project:

### 1. Clone the Repository
```bash
git clone https://github.com/your-repository/bcra_api.git
cd bcra_api
```

### 2. Build and Run with Docker Compose
Make sure Docker is running, and then execute:
```bash
docker-compose up --build
```
This command will:
- Build the FastAPI app image.
- Start the `fastapi_app` container on port 8010.
- Start the `postgres_db` container on port 5433, using PostgreSQL as the database.

### 3. Run the Project
To run the project in detached mode:
```bash
docker-compose up -d
```

### 4. Access the Database
To access the PostgreSQL database:
```bash
docker exec -it postgres_db psql -U user_bcra -d bcra_deudores
```

### 5. Create Tables Manually (Optional)
In case the tables are not generated automatically, create them manually using the following SQL commands:

#### Create `deudores` Table
```sql
CREATE TABLE deudores (
    id SERIAL PRIMARY KEY,
    codigo_entidad VARCHAR(5) NOT NULL,  -- Código de la entidad
    fecha_informacion VARCHAR(6) NOT NULL,  -- Fecha de la información en formato AAAAMM
    tipo_identificacion VARCHAR(2) NOT NULL,  -- Tipo de identificación (CUIT, CUIL, CDI)
    numero_identificacion VARCHAR(11) NOT NULL,  -- Número de identificación
    actividad VARCHAR(3) NOT NULL,  -- Código de actividad
    situacion INTEGER NOT NULL,  -- Situación del deudor
    prestamos_total_garantias NUMERIC(12, 1),  -- Préstamos/Total de garantías afrontadas
    sin_uso NUMERIC(12, 1),  -- Sin uso (campo sin uso)
    garantias_otorgadas NUMERIC(12, 1),  -- Garantías otorgadas
    otros_conceptos NUMERIC(12, 1),  -- Otros conceptos
    garantias_preferidas_a NUMERIC(12, 1),  -- Garantías preferidas "A"
    garantias_preferidas_b NUMERIC(12, 1),  -- Garantías preferidas "B"
    sin_garantias_preferidas NUMERIC(12, 1),  -- Sin garantías preferidas
    contragarantias_preferidas_a NUMERIC(12, 1),  -- Contragarantías preferidas "A"
    contragarantias_preferidas_b NUMERIC(12, 1),  -- Contragarantías preferidas "B"
    sin_contragarantias_preferidas NUMERIC(12, 1),  -- Sin contragarantías preferidas
    previsiones NUMERIC(12, 1),  -- Previsiones
    deuda_cubierta INTEGER NOT NULL,  -- Deuda cubierta (0: No, 1: Sí)
    proceso_judicial_revision INTEGER NOT NULL,  -- Proceso Judicial/Revisión (0: No, 1: Sí, 2: Revisión)
    refinanciaciones INTEGER NOT NULL,  -- Refinanciaciones (0: No, 1: Sí, 9: No aplicable)
    recategorizacion_obligatoria INTEGER NOT NULL,  -- Recategorización obligatoria (0: No, 1: Sí)
    situacion_juridica INTEGER NOT NULL,  -- Situación jurídica (0: No, 1: Sí, 9: No aplicable)
    irrecuperables_disposicion_tecnica INTEGER NOT NULL,  -- Irrecuperables por disposición técnica (0: No, 1: Sí, 9: No aplicable)
    dias_atraso INTEGER NOT NULL,  -- Días de atraso
    nombre_entidad VARCHAR(254) NOT NULL  -- Nombre de la entidad
);
```

#### Create `entidades` Table
```sql
CREATE TABLE entidades (
    id SERIAL PRIMARY KEY,
    codigo_entidad VARCHAR(5) UNIQUE NOT NULL,  -- Código de la entidad, único y no nulo
    nombre_entidad VARCHAR(70) NOT NULL  -- Nombre de la entidad, no nulo
);
```

#### Create `padrones` Table
```sql
CREATE TABLE padrones (
    id SERIAL PRIMARY KEY,
    identificacion VARCHAR(11) NOT NULL,
    denominacion VARCHAR(160) NOT NULL,
    actividad VARCHAR(6),
    marca_baja CHAR(1),
    cuit_reemplazo VARCHAR(11),
    fallecimiento CHAR(1)
);
```

### 6. Environment Details
The application reads from an environment variable to connect to the database:
- `DATABASE_URL`: The PostgreSQL connection string is set in the `docker-compose.yml` file.

### 7. API Endpoints
The project includes several endpoints for data interaction:
- **Upload Endpoint**: Allows users to upload and process data files.
- **Debtor Information Endpoint**: Retrieves debtor information based on provided identification.
- **Padron Processing Endpoint**: Processes large data files for integration into the database.

### 8. Example Commands
To test the API, you can use tools like `curl` or Postman. For example:
```bash
curl -X POST "http://localhost:8010/padron/upload" -H "Content-Type: multipart/form-data" -F "file=@path/to/padron.txt"
```

## File Details
### Docker Configuration (`docker-compose.yml`)
Defines the services for the FastAPI app and PostgreSQL database:
```yaml
version: '3.7'
services:
  web:
    build: .
    container_name: fastapi_app
    ports:
      - "8010:80"
    volumes:
      - ./app:/code/app
    depends_on:
      - db
    environment:
      DATABASE_URL: "postgresql://user_bcra:bcra1234@db/bcra_deudores"
  
  db:
    image: postgres
    container_name: postgres_db
    restart: always
    environment:
      POSTGRES_USER: user_bcra
      POSTGRES_PASSWORD: bcra1234
      POSTGRES_DB: bcra_deudores
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"
volumes:
  postgres_data:
```

### Requirements (`requirements.txt`)
Lists all Python dependencies:
```plaintext
fastapi
uvicorn
asyncpg
databases
SQLAlchemy
psycopg2
python-multipart
zipfile36
```

## Contact Information
**Librasoft SAS**  
Contact: [levislibra@libra-soft.com](mailto:levislibra@libra-soft.com)

---
Thank you for using **BCRA_API**. We hope this documentation helps you set up and manage your project seamlessly!

