from sqlalchemy import Column, Integer, Numeric, String

from app.database import Base


class Deudor(Base):
	__tablename__ = 'deudores'

	id = Column(Integer, primary_key=True, index=True)
	codigo_entidad = Column(String(5), nullable=False)  # Codigo de la entidad
	fecha_informacion = Column(String(6), nullable=False)  # Fecha de la informacion en formato AAAAMM
	tipo_identificacion = Column(String(2), nullable=False)  # Tipo de identificacion
	numero_identificacion = Column(String(11), nullable=False)
	actividad = Column(String(3), nullable=False)
	situacion = Column(Integer, nullable=False)
	prestamos_total_garantias = Column(Numeric(12, 1), nullable=True)
	sin_uso = Column(Numeric(12, 1), nullable=True)
	garantias_otorgadas = Column(Numeric(12, 1), nullable=True)
	otros_conceptos = Column(Numeric(12, 1), nullable=True)
	garantias_preferidas_a = Column(Numeric(12, 1), nullable=True)
	garantias_preferidas_b = Column(Numeric(12, 1), nullable=True)
	sin_garantias_preferidas = Column(Numeric(12, 1), nullable=True)
	contragarantias_preferidas_a = Column(Numeric(12, 1), nullable=True)
	contragarantias_preferidas_b = Column(Numeric(12, 1), nullable=True)
	sin_contragarantias_preferidas = Column(Numeric(12, 1), nullable=True)
	previsiones = Column(Numeric(12, 1), nullable=True)
	deuda_cubierta = Column(Integer, nullable=False)
	proceso_judicial_revision = Column(Integer, nullable=False)
	refinanciaciones = Column(Integer, nullable=False)
	recategorizacion_obligatoria = Column(Integer, nullable=False)
	situacion_juridica = Column(Integer, nullable=False)
	irrecuperables_disposicion_tecnica = Column(Integer, nullable=False)
	dias_atraso = Column(Integer, nullable=False)
	nombre_entidad = Column(String(254), nullable=False)


class Entidad(Base):
	__tablename__ = 'entidades'

	id = Column(Integer, primary_key=True, index=True)
	codigo_entidad = Column(String(5), unique=True, nullable=False)
	nombre_entidad = Column(String(70), nullable=False)


class Padron(Base):
	__tablename__ = 'padrones'

	id = Column(Integer, primary_key=True, index=True)
	identificacion = Column(String(11), nullable=False)
	denominacion = Column(String(160), nullable=False)
	actividad = Column(String(6), nullable=True)
	marca_baja = Column(String(1), nullable=True)
	cuit_reemplazo = Column(String(11), nullable=True)
	fallecimiento = Column(String(1), nullable=True)
