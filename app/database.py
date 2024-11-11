from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Declarar la URL de la base de datos
DATABASE_URL = "postgresql://user_bcra:bcra1234@bcra_db/bcra_deudores"
print(DATABASE_URL)  # Debugging
# Crear el motor de conexión
engine = create_engine(DATABASE_URL)

# Crear una sesión para interactuar con la base de datos
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para los modelos
Base = declarative_base()

# Función para obtener una sesión de la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()