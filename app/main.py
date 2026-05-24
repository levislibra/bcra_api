from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header, Form, status
from app.database import engine, Base
from sqlalchemy.orm import Session, sessionmaker
from fastapi.responses import HTMLResponse
from app.database import get_db
from app.import_jobs import create_deudores_job, get_job_status_payload, mark_incomplete_jobs_as_failed
from app.models import Entidad, Deudor, ImportJob, Padron
from app.settings import get_secret
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
mark_incomplete_jobs_as_failed()
print("Tablas creadas", flush=True)

# Define el token único que será usado para autenticar
SECRET_TOKEN = get_secret("SECRET_TOKEN")
PREFIJOS_CUIL = [
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
    "31", "32", "33", "34", "35", "36", "37", "38", "39", "40",
    "41", "42", "43", "44", "45", "46", "47", "48", "49", "50",
    "51", "52", "53", "54", "55", "56", "57", "58", "59", "60",
    "61", "62", "63", "64", "65", "66", "67", "68", "69", "70",
    "71", "72", "73", "74", "75", "76", "77", "78", "79", "80",
    "81", "82", "83", "84", "85", "86", "87", "88", "89", "90",
    "91", "92", "93", "94", "95", "96", "97", "98", "99"
]

@app.get("/")
async def read_root():
	return {"message": "Central de Deudores lista"}


@app.get("/health")
async def healthcheck():
	return {"status": "ok"}


@app.get("/api/validate-token")
async def validate_token(token: str):
	if token != SECRET_TOKEN:
		raise HTTPException(status_code=403, detail="Acceso denegado, token inválido")
	return {"valid": True}


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str, x_import_token: str = Header(..., alias="X-Import-Token"), db: Session = Depends(get_db)):
	if x_import_token != SECRET_TOKEN:
		raise HTTPException(status_code=403, detail="Acceso denegado, token inválido")

	job = db.get(ImportJob, job_id)
	if job is None:
		raise HTTPException(status_code=404, detail="Job no encontrado")

	return get_job_status_payload(job)

# *********************************************
# Consultas por API
# *********************************************

@app.get("/deudor/{numero_identificacion}")
async def get_deudor_info(numero_identificacion: str, db: Session = Depends(get_db)):
	logger.info(f"Buscando deudor con identificación {numero_identificacion}")

	if len(numero_identificacion) != 11:
		raise HTTPException(status_code=400, detail="Número de identificación inválido. Debe tener 11 dígitos (CUIL/CUIT).")

	posibles_cuits = [numero_identificacion]

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
		"numero_identificacion": deudas[0].numero_identificacion,
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

	if len(numero_identificacion) != 11:
		raise HTTPException(status_code=400, detail="Número de identificación inválido. Debe tener 11 dígitos (CUIL/CUIT).")

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
    return '''
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
                    min-height: 100vh;
                    margin: 0;
                    padding: 24px;
                }
                .form-container {
                    background-color: #fff;
                    padding: 24px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    max-width: 460px;
                    width: 100%;
                }
                h3 {
                    text-align: center;
                    color: #333;
                    margin-top: 0;
                }
                p.helper {
                    margin-top: 0;
                    margin-bottom: 18px;
                    color: #555;
                    font-size: 14px;
                    line-height: 1.5;
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
                    margin-bottom: 18px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    box-sizing: border-box;
                    font-size: 16px;
                }
                button[type="submit"] {
                    width: 100%;
                    background-color: #28a745;
                    color: white;
                    padding: 10px;
                    border: none;
                    border-radius: 5px;
                    font-size: 16px;
                    cursor: pointer;
                }
                button[type="submit"]:hover {
                    background-color: #218838;
                }
                button[type="submit"]:disabled {
                    background-color: #93c5a1;
                    cursor: not-allowed;
                }
                .message {
                    display: none;
                    padding: 10px;
                    margin: 0 0 12px 0;
                    border-radius: 5px;
                    font-size: 14px;
                }
                .message.error {
                    display: block;
                    background-color: #fde8e8;
                    color: #b91c1c;
                }
                .message.info {
                    display: block;
                    background-color: #e8f1fd;
                    color: #1d4ed8;
                }
                .message.success {
                    display: block;
                    background-color: #e9f9ee;
                    color: #166534;
                }
                .progress-wrapper {
                    display: none;
                    margin-bottom: 12px;
                }
                .progress-wrapper.visible {
                    display: block;
                }
                .progress-header {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 8px;
                    font-size: 14px;
                    color: #555;
                }
                .progress-track {
                    width: 100%;
                    height: 14px;
                    background-color: #e5e7eb;
                    border-radius: 999px;
                    overflow: hidden;
                }
                .progress-bar {
                    width: 0%;
                    height: 100%;
                    background: linear-gradient(90deg, #2563eb, #16a34a);
                    transition: width 0.2s ease;
                }
                .job-meta {
                    margin-top: 8px;
                    color: #666;
                    font-size: 13px;
                    min-height: 18px;
                }
            </style>
        </head>
        <body>
            <div class="form-container">
                <h3>Subir archivos de deudores y entidades</h3>
                <p class="helper">La carga se ejecuta en background. Cuando termine la subida, el servidor crea un job y podés seguir el progreso sin dejar la request del navegador abierta.</p>
                <form id="upload-form" action="/deudores/upload/" enctype="multipart/form-data" method="post">
                    <label for="deudores">Archivo Deudores (.zip):</label>
                    <input type="file" id="deudores" name="deudores" accept=".zip" required>

                    <label for="entidades">Archivo Entidades:</label>
                    <input type="file" id="entidades" name="entidades" required>

                    <label for="token">Token de seguridad:</label>
                    <input type="text" id="token" name="token" placeholder="Ingresá tu token" required>

                    <div id="message" class="message" role="alert" aria-live="polite"></div>
                    <div id="progress-wrapper" class="progress-wrapper" aria-live="polite">
                        <div class="progress-header">
                            <span id="progress-label">Progreso</span>
                            <span id="progress-text">0%</span>
                        </div>
                        <div class="progress-track">
                            <div id="progress-bar" class="progress-bar"></div>
                        </div>
                        <div id="job-meta" class="job-meta"></div>
                    </div>
                    <button id="submit-button" type="submit">Cargar archivos</button>
                </form>
            </div>
            <script>
                const form = document.getElementById("upload-form");
                const submitButton = document.getElementById("submit-button");
                const progressWrapper = document.getElementById("progress-wrapper");
                const progressBar = document.getElementById("progress-bar");
                const progressText = document.getElementById("progress-text");
                const progressLabel = document.getElementById("progress-label");
                const message = document.getElementById("message");
                const jobMeta = document.getElementById("job-meta");
                const deudoresInput = document.getElementById("deudores");
                const entidadesInput = document.getElementById("entidades");

                function setMessage(text, type) {
                    message.textContent = text;
                    message.className = "message " + type;
                }

                function clearMessage() {
                    message.textContent = "";
                    message.className = "message";
                }

                function setProgress(value) {
                    const safeValue = Math.max(0, Math.min(100, value));
                    progressBar.style.width = safeValue + "%";
                    progressText.textContent = safeValue + "%";
                }

                function setJobMeta(text) {
                    jobMeta.textContent = text || "";
                }

                function toggleUploadingState(isUploading) {
                    submitButton.disabled = isUploading;
                    form.querySelectorAll("input").forEach((input) => {
                        input.disabled = isUploading;
                    });
                }

                async function validateToken(token) {
                    const response = await fetch("/api/validate-token?token=" + encodeURIComponent(token), {
                        method: "GET",
                        cache: "no-store"
                    });

                    if (!response.ok) {
                        let detail = "No se pudo validar el token.";
                        try {
                            const data = await response.json();
                            detail = data.detail || detail;
                        } catch (error) {
                            console.error(error);
                        }
                        throw new Error(detail);
                    }
                }

                async function pollJob(jobId, token) {
                    try {
                        const response = await fetch("/jobs/" + encodeURIComponent(jobId), {
                            method: "GET",
                            cache: "no-store",
                            headers: {
                                "X-Import-Token": token
                            }
                        });

                        if (!response.ok) {
                            let detail = "No se pudo consultar el estado del job.";
                            try {
                                const data = await response.json();
                                detail = data.detail || detail;
                            } catch (error) {
                                console.error(error);
                            }
                            throw new Error(detail);
                        }

                        const data = await response.json();
                        progressLabel.textContent = "Procesamiento";
                        setProgress(data.progress_percent || 0);
                        setJobMeta("Job: " + data.job_id + " | Etapa: " + data.stage + " | Filas: " + (data.processed_rows || 0).toLocaleString("es-AR"));

                        if (data.status === "completed") {
                            setProgress(100);
                            setMessage(data.message || "Archivos procesados correctamente.", "success");
                            toggleUploadingState(false);
                            form.reset();
                            return;
                        }

                        if (data.status === "failed") {
                            setMessage(data.error || data.message || "El job falló durante el procesamiento.", "error");
                            toggleUploadingState(false);
                            return;
                        }

                        setMessage(data.message || "Procesando archivos en segundo plano...", "info");
                        window.setTimeout(() => pollJob(jobId, token), 2000);
                    } catch (error) {
                        setMessage((error && error.message) || "Error consultando el estado del job. Reintentando...", "info");
                        window.setTimeout(() => pollJob(jobId, token), 3000);
                    }
                }

                form.addEventListener("submit", async (event) => {
                    event.preventDefault();
                    clearMessage();
                    setJobMeta("");
                    setProgress(0);
                    progressLabel.textContent = "Subida";
                    progressWrapper.classList.remove("visible");

                    const formData = new FormData(form);
                    const token = formData.get("token");
                    const deudoresFile = deudoresInput.files[0];
                    const entidadesFile = entidadesInput.files[0];

                    if (!deudoresFile || !entidadesFile) {
                        setMessage("Seleccioná ambos archivos antes de continuar.", "error");
                        return;
                    }

                    if (!token) {
                        setMessage("Ingresá el token de seguridad.", "error");
                        return;
                    }

                    if (!deudoresFile.name.toLowerCase().endsWith(".zip")) {
                        setMessage("El archivo de deudores debe ser un .zip válido.", "error");
                        return;
                    }

                    toggleUploadingState(true);
                    setMessage("Validando token...", "info");

                    try {
                        await validateToken(token);
                    } catch (error) {
                        toggleUploadingState(false);
                        setMessage(error.message || "Token inválido.", "error");
                        return;
                    }

                    progressWrapper.classList.add("visible");
                    setMessage("Subiendo archivos...", "info");

                    const xhr = new XMLHttpRequest();
                    xhr.open("POST", form.action);

                    xhr.upload.addEventListener("progress", (progressEvent) => {
                        if (!progressEvent.lengthComputable) {
                            return;
                        }

                        const percentage = Math.round((progressEvent.loaded / progressEvent.total) * 100);
                        setProgress(percentage);

                        if (percentage === 100) {
                            setMessage("Subida completa. Creando job en el servidor...", "info");
                        }
                    });

                    xhr.addEventListener("load", () => {
                        if (xhr.status >= 200 && xhr.status < 300) {
                            let data = null;
                            try {
                                data = JSON.parse(xhr.responseText);
                            } catch (error) {
                                console.error(error);
                            }

                            if (!data || !data.job_id) {
                                toggleUploadingState(false);
                                setMessage("La respuesta del servidor no incluyó el job de importación.", "error");
                                return;
                            }

                            setProgress(0);
                            progressLabel.textContent = "Procesamiento";
                            setMessage(data.message || "Archivos subidos. Procesando en background...", "info");
                            setJobMeta("Job: " + data.job_id + " | Etapa: " + data.stage);
                            pollJob(data.job_id, token);
                            return;
                        }

                        toggleUploadingState(false);

                        let detail = "Ocurrió un error al cargar los archivos.";
                        try {
                            const data = JSON.parse(xhr.responseText);
                            detail = data.detail || data.message || detail;
                        } catch (error) {
                            console.error(error);
                        }
                        setMessage(detail, "error");
                    });

                    xhr.addEventListener("error", () => {
                        toggleUploadingState(false);
                        setMessage("Error de red durante la carga. Revisá la conexión e intentá nuevamente.", "error");
                    });

                    xhr.send(formData);
                });
            </script>
        </body>
    </html>
    '''


@app.post("/deudores/upload/", status_code=status.HTTP_202_ACCEPTED)
async def upload_files(
    deudores: UploadFile = File(...),
    entidades: UploadFile = File(...),
    token: str = Form(...),
):
    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Acceso denegado, token inválido")

    job = create_deudores_job(deudores=deudores, entidades=entidades)
    return get_job_status_payload(job)


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
	logger.info(f"Procesando archivo Padrón ***************")
	# Verificar el token
	if token != SECRET_TOKEN:
		raise HTTPException(status_code=403, detail="Acceso denegado, token inválido")
	logger.info(f"Token correcto.")
	logger.info(f"Procesando archivo Padrón...")
	# Procesar el archivo de padrón
	process_padron(padron.file, db)
	logger.info(f"Archivo Padrón procesado correctamente.")
	return {"message": "Archivo Padrón procesado correctamente"}

def process_padron(padron_file, db, batch_size=5000):
	logger.info("Processing padron file...")

	# Eliminar todos los registros de la tabla antes de cargar los nuevos datos
	db.query(Padron).delete()
	db.commit()
	logger.info(f"All existing records deleted from padrones table.")

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
	posibles_identificaciones = [identificacion]
	# Determinar si la identificación es un DNI (8 dígitos) o un CUIT/CUIL (11 dígitos)
	if len(identificacion) == 8 and identificacion.isdigit():
		# Generar posibles CUITs con prefijos comunes y calcular el dígito verificador
		for prefijo in PREFIJOS_CUIL:
			posibles_identificaciones.append(str(prefijo) + str(identificacion) + str(calcular_digito_verificador(prefijo + identificacion)))
	
	logger.info(f"Posibles identificaciones a buscar: {posibles_identificaciones}")

	# Buscar en la base de datos por las identificaciones generadas
	registros = db.query(Padron).filter(Padron.identificacion.in_(posibles_identificaciones)).all()
	logger.info(f"Registro encontrado: {registros}")
	if not registros:
		raise HTTPException(status_code=404, detail="Registro no encontrado")

	# Tomar el tiempo de fin y calcular la duración
	end_time = time.time()
	duration = end_time - start_time

	# Formatear la respuesta
	padrones = []
	for registro in registros:
		padrones.append({
			"id": registro.id,
			"identificacion": registro.identificacion,
			"denominacion": registro.denominacion,
			"actividad": registro.actividad,
			"marca_baja": registro.marca_baja,
			"cuit_reemplazo": registro.cuit_reemplazo,
			"fallecimiento": registro.fallecimiento
		})
	return {
		"resultado": padrones,
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
		"resultado": respuesta,
		"tiempo_demora_segundos": duration
	}
