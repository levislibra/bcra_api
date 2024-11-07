from sqlalchemy import Column, Integer, String, Numeric
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Deudor(Base):
	__tablename__ = 'deudores'

	id = Column(Integer, primary_key=True, index=True)
	codigo_entidad = Column(String(5), nullable=False)  # Código de la entidad
	fecha_informacion = Column(String(6), nullable=False)  # Fecha de la información en formato AAAAMM
	tipo_identificacion = Column(String(2), nullable=False)  # Tipo de identificación (CUIT, CUIL, CDI)
	numero_identificacion = Column(String(11), nullable=False)  # Número de identificación
	actividad = Column(String(3), nullable=False)  # Código de actividad
	situacion = Column(Integer, nullable=False)  # Situación del deudor
	prestamos_total_garantias = Column(Numeric(12, 1), nullable=True)  # Préstamos/Total de garantías afrontadas
	sin_uso = Column(Numeric(12, 1), nullable=True)  # Sin uso (campo sin uso)
	garantias_otorgadas = Column(Numeric(12, 1), nullable=True)  # Garantías otorgadas
	otros_conceptos = Column(Numeric(12, 1), nullable=True)  # Otros conceptos
	garantias_preferidas_a = Column(Numeric(12, 1), nullable=True)  # Garantías preferidas "A"
	garantias_preferidas_b = Column(Numeric(12, 1), nullable=True)  # Garantías preferidas "B"
	sin_garantias_preferidas = Column(Numeric(12, 1), nullable=True)  # Sin garantías preferidas
	contragarantias_preferidas_a = Column(Numeric(12, 1), nullable=True)  # Contragarantías preferidas "A"
	contragarantias_preferidas_b = Column(Numeric(12, 1), nullable=True)  # Contragarantías preferidas "B"
	sin_contragarantias_preferidas = Column(Numeric(12, 1), nullable=True)  # Sin contragarantías preferidas
	previsiones = Column(Numeric(12, 1), nullable=True)  # Previsiones
	deuda_cubierta = Column(Integer, nullable=False)  # Deuda cubierta (0: No, 1: Sí)
	proceso_judicial_revision = Column(Integer, nullable=False)  # Proceso Judicial/Revisión (0: No, 1: Sí, 2: Revisión)
	refinanciaciones = Column(Integer, nullable=False)  # Refinanciaciones (0: No, 1: Sí, 9: No aplicable)
	recategorizacion_obligatoria = Column(Integer, nullable=False)  # Recategorización obligatoria (0: No, 1: Sí)
	situacion_juridica = Column(Integer, nullable=False)  # Situación jurídica (0: No, 1: Sí, 9: No aplicable)
	irrecuperables_disposicion_tecnica = Column(Integer, nullable=False)  # Irrecuperables por disposición técnica (0: No, 1: Sí, 9: No aplicable)
	dias_atraso = Column(Integer, nullable=False)  # Días de atraso
	# adicionales
	nombre_entidad = Column(String(254), nullable=False)  # Nombre de la entidad

class Entidad(Base):
	__tablename__ = 'entidades'

	id = Column(Integer, primary_key=True, index=True)
	codigo_entidad = Column(String(5), unique=True, nullable=False)
	nombre_entidad = Column(String(70), nullable=False)

class Padron(Base):
	__tablename__ = "padrones"
	
	id = Column(Integer, primary_key=True, index=True)
	identificacion = Column(String(11), nullable=False)  # CUIT/CUIL/CDI
	denominacion = Column(String(160), nullable=False)
	actividad = Column(String(6), nullable=True)
	marca_baja = Column(String(1), nullable=True)
	cuit_reemplazo = Column(String(11), nullable=True)
	fallecimiento = Column(String(1), nullable=True)