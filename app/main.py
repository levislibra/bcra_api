from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header, Form
from app.database import engine, Base
from sqlalchemy.orm import Session, sessionmaker
from fastapi.responses import HTMLResponse
from app.database import get_db
from app.models import Entidad, Deudor, Padron
from sqlalchemy import and_, func
from typing import List
from contextlib import contextmanager
import zipfile
import time
import tempfile
import logging
# from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

app = FastAPI()

# Crear las tablas en la base de datos
print("Creando tablas...", flush=True)  # Debugging
Base.metadata.create_all(bind=engine)
print("Tablas creadas", flush=True)

# Define el token único que será usado para autenticar
SECRET_TOKEN = "1234"

@app.get("/")
async def read_root():
	return {"message": "Central de Deudores lista"}

# *********************************************
# Consultas por API
# *********************************************

@app.get("/deudor/{numero_identificacion}")
async def get_deudor_info(numero_identificacion: str, db: Session = Depends(get_db)):
	logger.info(f"Buscando deudor con identificación {numero_identificacion}")

	# Determinar si la identificación es CUIT o DNI
	if len(numero_identificacion) == 8:
		# Generar posibles CUIT con prefijos comunes y el dígito verificador correcto
		prefijos = ["20", "23", "24", "27"]
		posibles_cuits = [
			f"{prefijo}{numero_identificacion}{calcular_digito_verificador(f'{prefijo}{numero_identificacion}')}"
			for prefijo in prefijos
		]
	else:
		posibles_cuits = [numero_identificacion]
	
	logger.info(f"Posibles CUITs: {posibles_cuits}")

	# Obtener la fecha más reciente de información para el deudor
	max_fecha = db.query(func.max(Deudor.fecha_informacion)).filter(
		Deudor.numero_identificacion.in_(posibles_cuits)
	).scalar()
	logger.info(f"Fecha más reciente: {max_fecha}")

	if not max_fecha:
		raise HTTPException(status_code=404, detail="Deudor no encontrado o sin registros recientes")

	# Obtener todas las entradas que coincidan con la fecha más reciente y el número de identificación
	deudas = db.query(Deudor).filter(
		Deudor.numero_identificacion.in_(posibles_cuits),
		Deudor.fecha_informacion == max_fecha
	).all()
	logger.info(f"Deudas encontradas: {len(deudas)}")

	# Si no se encuentran deudas
	if not deudas:
		raise HTTPException(status_code=404, detail="No se encontraron registros para la fecha más reciente")

	# Formar la respuesta con todas las deudas del deudor en la fecha más reciente
	return {
		"numero_identificacion": numero_identificacion,
		"fecha_informacion": max_fecha,
		"monto_situacion_1": sum(deuda.prestamos_total_garantias for deuda in deudas if deuda.situacion == 1),
		"monto_situacion_2": sum(deuda.prestamos_total_garantias for deuda in deudas if deuda.situacion == 2),
		"monto_situacion_3": sum(deuda.prestamos_total_garantias for deuda in deudas if deuda.situacion == 3),
		"monto_situacion_4": sum(deuda.prestamos_total_garantias for deuda in deudas if deuda.situacion == 4),
		"monto_situacion_5": sum(deuda.prestamos_total_garantias for deuda in deudas if deuda.situacion == 5),
		"deudas": [
			{
				"situacion": deuda.situacion,
				"monto": deuda.prestamos_total_garantias,
				"banco": deuda.nombre_entidad
			}
			for deuda in deudas
		]
	}

@app.get("/deudor/{numero_identificacion}/peor_situacion")
async def get_peor_situacion(numero_identificacion: str, db: Session = Depends(get_db)):
	logger.info(f"Buscando peor situación para identificación {numero_identificacion}")

	# Determinar si la identificación es CUIT o DNI
	if len(numero_identificacion) == 8:
		# Generar posibles CUIT con prefijos comunes y el dígito verificador correcto
		prefijos = ["20", "23", "24", "27"]
		posibles_cuits = [
			f"{prefijo}{numero_identificacion}{calcular_digito_verificador(f'{prefijo}{numero_identificacion}')}"
			for prefijo in prefijos
		]
	else:
		posibles_cuits = [numero_identificacion]

	logger.info(f"Posibles CUITs: {posibles_cuits}")

	# Obtener la fecha más reciente de información para el deudor
	max_fecha = db.query(func.max(Deudor.fecha_informacion)).filter(
		Deudor.numero_identificacion.in_(posibles_cuits)
	).scalar()
	logger.info(f"Fecha más reciente: {max_fecha}")

	if not max_fecha:
		raise HTTPException(status_code=404, detail="Deudor no encontrado o sin registros recientes")

	# Obtener la peor situación del deudor en la fecha más reciente
	peor_situacion = db.query(func.max(Deudor.situacion)).filter(
		Deudor.numero_identificacion.in_(posibles_cuits),
		Deudor.fecha_informacion == max_fecha
	).scalar()

	if peor_situacion is None:
		raise HTTPException(status_code=404, detail="No se encontró información de situación para el deudor")

	return {
		"numero_identificacion": numero_identificacion,
		"fecha_informacion": max_fecha,
		"peor_situacion": peor_situacion
	}

# *********************************************
# Funciones auxiliares
# *********************************************

def calcular_digito_verificador(cuit_base: str) -> str:
	# Pesos para el cálculo del dígito verificador
	pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
	acumulador = sum(int(digito) * peso for digito, peso in zip(cuit_base, pesos))
	verificador = 11 - (acumulador % 11)
	if verificador == 11:
		verificador = 0
	elif verificador == 10:
		verificador = 9  # Ajuste común en algunos sistemas para casos donde el verificador resulta en 10
	return str(verificador)

# *********************************************
# Carga de archivos
# *********************************************

# Endpoint GET para renderizar un formulario HTML
@app.get("/deudores/upload", response_class=HTMLResponse)
async def get_upload_form():
	return """
	<html>
		<head>
			<title>Subir archivos</title>
			<style>
				body {
					font-family: Arial, sans-serif;
					background-color: #f4f4f9;
					display: flex;
					justify-content: center;
					align-items: center;
					height: 100vh;
				}
				.form-container {
					background-color: #fff;
					padding: 20px;
					border-radius: 10px;
					box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
					max-width: 400px;
					width: 100%;
				}
				h3 {
					text-align: center;
					color: #333;
				}
				label {
					display: block;
					margin-bottom: 8px;
					color: #555;
				}
				input[type="file"],
				input[type="text"] {
					width: 100%;
					padding: 10px;
					margin-bottom: 20px;
					border: 1px solid #ccc;
					border-radius: 5px;
					box-sizing: border-box;
					font-size: 16px;
				}
				input[type="submit"] {
					width: 100%;
					background-color: #28a745;
					color: white;
					padding: 10px;
					border: none;
					border-radius: 5px;
					font-size: 16px;
					cursor: pointer;
				}
				input[type="submit"]:hover {
					background-color: #218838;
				}
				.form-group {
					margin-bottom: 20px;
				}
			</style>
		</head>
		<body>
			<div class="form-container">
				<h3>Subir archivos de deudores y entidades</h3>
				<form action="/upload/" enctype="multipart/form-data" method="post">
					<div class="form-group">
						<label for="deudores">Archivo Deudores:</label>
						<input type="file" id="deudores" name="deudores" required>
					</div>
					<div class="form-group">
						<label for="entidades">Archivo Entidades:</label>
						<input type="file" id="entidades" name="entidades" required>
					</div>
					<div class="form-group">
						<label for="token">Token de seguridad:</label>
						<input type="text" id="token" name="token" placeholder="Ingresa tu token" required>
					</div>
					<input type="submit" value="Cargar archivos">
				</form>
			</div>
		</body>
	</html>
	"""

@app.post("/deudores/upload/")
async def upload_files(
	deudores: UploadFile = File(...), 
	entidades: UploadFile = File(...), 
	token: str = Form(...),  # Leer el token desde el formulario en lugar del encabezado
	db: Session = Depends(get_db)
):
	# Verificar el token
	if token != SECRET_TOKEN:
		raise HTTPException(status_code=403, detail="Acceso denegado, token inválido")

	# Procesar primero el archivo de entidades
	process_entidades(entidades.file, db)
	
	# Luego procesar el archivo de deudores
	process_deudores(deudores.file, db)

	return {"message": "Archivos procesados correctamente"}


def load_entidades(db):
	# Cargar todas las entidades en un diccionario para reducir consultas repetidas
	entidades = db.query(Entidad).all()
	return {entidad.codigo_entidad: entidad.nombre_entidad for entidad in entidades}

def process_deudores(deudores_file, db, batch_size=500):
	print("Processing deudores file...", flush=True)

	# Precargar entidades en memoria
	entidades_dict = load_entidades(db)

	with tempfile.TemporaryFile() as temp_file:
		temp_file.write(deudores_file.read())
		temp_file.seek(0)

		with zipfile.ZipFile(temp_file) as z:
			with z.open('deudores.txt') as deudores_txt:
				batch = []
				line_count = 0

				# Leer el archivo línea por línea sin ThreadPoolExecutor
				for line in deudores_txt:
					line = line.decode("ISO-8859-1")

					# Extraer los campos necesarios de la línea
					codigo_entidad = line[0:5].strip()
					fecha_informacion = line[5:11].strip()
					tipo_identificacion = line[11:13].strip()
					numero_identificacion = line[13:24].strip()
					actividad = line[24:27].strip()
					situacion = int(line[27:29].strip() or "0")
					prestamos_total_garantias = float(line[29:41].strip().replace(',', '.')) if line[29:41].strip() else None
					sin_uso = float(line[41:53].strip().replace(',', '.')) if line[41:53].strip() else None
					garantias_otorgadas = float(line[53:65].strip().replace(',', '.')) if line[53:65].strip() else None
					otros_conceptos = float(line[65:77].strip().replace(',', '.')) if line[65:77].strip() else None
					garantias_preferidas_a = float(line[77:89].strip().replace(',', '.')) if line[77:89].strip() else None
					garantias_preferidas_b = float(line[89:101].strip().replace(',', '.')) if line[89:101].strip() else None
					sin_garantias_preferidas = float(line[101:113].strip().replace(',', '.')) if line[101:113].strip() else None
					contragarantias_preferidas_a = float(line[113:125].strip().replace(',', '.')) if line[113:125].strip() else None
					contragarantias_preferidas_b = float(line[125:137].strip().replace(',', '.')) if line[125:137].strip() else None
					sin_contragarantias_preferidas = float(line[137:149].strip().replace(',', '.')) if line[137:149].strip() else None
					previsiones = float(line[149:161].strip().replace(',', '.')) if line[149:161].strip() else None
					deuda_cubierta = int(line[161:162].strip())
					proceso_judicial_revision = int(line[162:163].strip())
					refinanciaciones = int(line[163:164].strip())
					recategorizacion_obligatoria = int(line[164:165].strip())
					situacion_juridica = int(line[165:166].strip())
					irrecuperables_disposicion_tecnica = int(line[166:167].strip())
					dias_atraso = int(line[167:170].strip())

					# Obtener el nombre de la entidad del diccionario precargado
					nombre_entidad = entidades_dict.get(codigo_entidad, "Desconocida")

					# Agregar al lote
					batch.append({
						"codigo_entidad": codigo_entidad,
						"fecha_informacion": fecha_informacion,
						"tipo_identificacion": tipo_identificacion,
						"numero_identificacion": numero_identificacion,
						"actividad": actividad,
						"situacion": situacion,
						"prestamos_total_garantias": prestamos_total_garantias,
						"sin_uso": sin_uso,
						"garantias_otorgadas": garantias_otorgadas,
						"otros_conceptos": otros_conceptos,
						"garantias_preferidas_a": garantias_preferidas_a,
						"garantias_preferidas_b": garantias_preferidas_b,
						"sin_garantias_preferidas": sin_garantias_preferidas,
						"contragarantias_preferidas_a": contragarantias_preferidas_a,
						"contragarantias_preferidas_b": contragarantias_preferidas_b,
						"sin_contragarantias_preferidas": sin_contragarantias_preferidas,
						"previsiones": previsiones,
						"deuda_cubierta": deuda_cubierta,
						"proceso_judicial_revision": proceso_judicial_revision,
						"refinanciaciones": refinanciaciones,
						"recategorizacion_obligatoria": recategorizacion_obligatoria,
						"situacion_juridica": situacion_juridica,
						"irrecuperables_disposicion_tecnica": irrecuperables_disposicion_tecnica,
						"dias_atraso": dias_atraso,
						"nombre_entidad": nombre_entidad
					})

					line_count += 1

					# Procesar el lote cuando alcanza el tamaño definido
					if len(batch) >= batch_size:
						save_batch_deudor(db, batch)
						logger.info(f"Processed {line_count} lines so far")
						batch.clear()  # Limpiar el lote para el siguiente

				# Procesar cualquier lote restante
				if batch:
					save_batch_deudor(db, batch)
					logger.info(f"Processed {line_count} lines in total")
					batch.clear()

def save_batch_deudor(db, batch):
    db.bulk_insert_mappings(Deudor, batch)
    db.commit()

# *********************************************
# Entidades
# *********************************************

def process_entidades(entidades_file, db):
	# Leer el archivo completo y convertirlo a un formato de texto con ISO-8859-1 (o UTF-8 si funciona)
	content = entidades_file.read().decode("ISO-8859-1")  # o UTF-8 si no hay problemas

	# Procesar línea por línea
	for line in content.splitlines():
		# Los primeros 5 caracteres son el código de la entidad, el resto es el nombre
		codigo_entidad = line[0:5].strip()  # Ahora tratado como String
		nombre_entidad = line[5:].strip()

		# Verificar si la entidad ya existe en la base de datos
		entidad_existente = db.query(Entidad).filter(Entidad.codigo_entidad == codigo_entidad).first()

		if entidad_existente:
			# Si la entidad existe, actualiza su nombre
			entidad_existente.nombre_entidad = nombre_entidad
		else:
			# Si no existe, crea una nueva entidad
			nueva_entidad = Entidad(
				codigo_entidad=codigo_entidad,
				nombre_entidad=nombre_entidad
			)
			db.add(nueva_entidad)
	
	db.commit()


# *********************************************
# Padron AFIP
# *********************************************

@app.get("/padron/upload", response_class=HTMLResponse)
async def get_padron_upload_form():
	return """
	<html>
		<head>
			<title>Subir archivo Padrón</title>
			<style>
				body {
					font-family: Arial, sans-serif;
					background-color: #f4f4f9;
					display: flex;
					justify-content: center;
					align-items: center;
					height: 100vh;
				}
				.form-container {
					background-color: #fff;
					padding: 20px;
					border-radius: 10px;
					box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
					max-width: 400px;
					width: 100%;
				}
				h3 {
					text-align: center;
					color: #333;
				}
				label {
					display: block;
					margin-bottom: 8px;
					color: #555;
				}
				input[type="file"],
				input[type="text"] {
					width: 100%;
					padding: 10px;
					margin-bottom: 20px;
					border: 1px solid #ccc;
					border-radius: 5px;
					box-sizing: border-box;
					font-size: 16px;
				}
				input[type="submit"] {
					width: 100%;
					background-color: #28a745;
					color: white;
					padding: 10px;
					border: none;
					border-radius: 5px;
					font-size: 16px;
					cursor: pointer;
				}
				input[type="submit"]:hover {
					background-color: #218838;
				}
				.form-group {
					margin-bottom: 20px;
				}
			</style>
		</head>
		<body>
			<div class="form-container">
				<h3>Subir archivo de Padrón</h3>
				<form action="/padron/upload/" enctype="multipart/form-data" method="post">
					<div class="form-group">
						<label for="padron">Archivo Padrón (.zip):</label>
						<input type="file" id="padron" name="padron" required>
					</div>
					<div class="form-group">
						<label for="token">Token de seguridad:</label>
						<input type="text" id="token" name="token" placeholder="Ingresa tu token" required>
					</div>
					<input type="submit" value="Cargar archivo">
				</form>
			</div>
		</body>
	</html>
	"""

@app.post("/padron/upload")
async def upload_padron(
	padron: UploadFile = File(...), 
	token: str = Form(...),  # Leer el token desde el formulario
	db: Session = Depends(get_db)
):
	# Verificar el token
	if token != SECRET_TOKEN:
		raise HTTPException(status_code=403, detail="Acceso denegado, token inválido")

	# Procesar el archivo de padrón
	process_padron(padron.file, db)

	return {"message": "Archivo Padrón procesado correctamente"}

def process_padron(padron_file, db, batch_size=5000):
	print("Processing padron file...", flush=True)

	# Eliminar todos los registros de la tabla antes de cargar los nuevos datos
	db.query(Padron).delete()
	db.commit()
	print("All existing records deleted from padrones table.", flush=True)

	# Crear un archivo temporal para manejar el contenido del archivo subido
	with tempfile.TemporaryFile() as temp_file:
		temp_file.write(padron_file.read())
		temp_file.seek(0)

		# Descomprimir el archivo .zip y procesar padron.txt
		with zipfile.ZipFile(temp_file) as z:
			with z.open('padron.txt') as padron_txt:
				batch = []
				line_count = 0

				# Leer el archivo línea por línea
				for line in padron_txt:
					# Cambiar la codificación a ISO-8859-1
					line = line.decode("ISO-8859-1").strip()

					# Extraer los campos necesarios de la línea
					identificacion = line[0:11].strip()
					denominacion = line[11:171].strip()
					actividad = line[171:177].strip()
					marca_baja = line[177:178].strip()
					cuit_reemplazo = line[178:189].strip()
					fallecimiento = line[189:190].strip()

					# Agregar al lote
					batch.append({
						"identificacion": identificacion,
						"denominacion": denominacion,
						"actividad": actividad,
						"marca_baja": marca_baja,
						"cuit_reemplazo": cuit_reemplazo,
						"fallecimiento": fallecimiento
					})

					line_count += 1

					# Procesar el lote cuando alcanza el tamaño definido
					if len(batch) >= batch_size:
						save_batch_padron(db, batch)
						logger.info(f"Processed {line_count} lines so far")
						batch.clear()  # Limpiar el lote para el siguiente

				# Procesar cualquier lote restante
				if batch:
					save_batch_padron(db, batch)
					logger.info(f"Processed {line_count} lines in total")
					batch.clear()

	print(f"Total de líneas procesadas: {line_count}")

def save_batch_padron(db, batch):
	db.bulk_insert_mappings(Padron, batch)
	db.commit()

# *********************************************
# Consultas por API
# *********************************************

@app.get("/padron/{identificacion}")
async def get_padron_by_identificacion(identificacion: str, db: Session = Depends(get_db)):
	# Tomar el tiempo de inicio
	start_time = time.time()

	# logger.info(f"Buscando detalle del padrón para identificación {identificacion}")

	# Determinar si la identificación es un DNI (8 dígitos) o un CUIT/CUIL (11 dígitos)
	if len(identificacion) == 8 and identificacion.isdigit():
		# Generar posibles CUITs con prefijos comunes y calcular el dígito verificador
		prefijos = ["20", "23", "24", "27"]
		posibles_cuits = [
			f"{prefijo}{identificacion}{calcular_digito_verificador(f'{prefijo}{identificacion}')}"
			for prefijo in prefijos
		]
		posibles_identificaciones = [identificacion] + posibles_cuits
	else:
		posibles_identificaciones = [identificacion]

	# logger.info(f"Posibles identificaciones a buscar: {posibles_identificaciones}")

	# Buscar en la base de datos por las identificaciones generadas
	registro = db.query(Padron).filter(Padron.identificacion.in_(posibles_identificaciones)).first()

	if not registro:
		raise HTTPException(status_code=404, detail="Registro no encontrado")

	# Tomar el tiempo de fin y calcular la duración
	end_time = time.time()
	duration = end_time - start_time


	return {
		"id": registro.id,
		"identificacion": registro.identificacion,
		"denominacion": registro.denominacion,
		"actividad": registro.actividad,
		"marca_baja": registro.marca_baja,
		"cuit_reemplazo": registro.cuit_reemplazo,
		"fallecimiento": registro.fallecimiento,
		"tiempo_demora_segundos": duration
	}

@app.get("/padron/nombre/{nombre_apellido}")
async def get_padron_by_nombre(nombre_apellido: str, db: Session = Depends(get_db)):
	# Tomar el tiempo de inicio
	start_time = time.time()

	# Dividir el nombre y apellido en palabras clave
	palabras_clave = nombre_apellido.split()

	# Crear una condición que verifique que cada palabra clave esté en la denominación
	condiciones = [Padron.denominacion.ilike(f"%{palabra}%") for palabra in palabras_clave]

	# Ejecutar la consulta usando AND para buscar todas las palabras en cualquier orden
	registros = db.query(Padron).filter(and_(*condiciones)).all()

	if not registros:
		raise HTTPException(status_code=404, detail="No se encontraron registros")

	# Tomar el tiempo de fin y calcular la duración
	end_time = time.time()
	duration = end_time - start_time

	# Formatear la respuesta
	respuesta = []
	for registro in registros:
		respuesta.append({
			"id": registro.id,
			"identificacion": registro.identificacion,
			"denominacion": registro.denominacion,
			"actividad": registro.actividad,
			"marca_baja": registro.marca_baja,
			"cuit_reemplazo": registro.cuit_reemplazo,
			"fallecimiento": registro.fallecimiento
		})

	return {
		"resultados": respuesta,
		"tiempo_demora_segundos": duration
	}
