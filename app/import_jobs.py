from __future__ import annotations

import io
import logging
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Deudor, Entidad, ImportJob

logger = logging.getLogger("uvicorn.error")

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024
DEUDORES_COPY_BATCH_SIZE = 50_000
DEUDORES_ZIP_MEMBER = "deudores.txt"
JOB_TYPE_DEUDORES = "deudores"
ACTIVE_JOB_STATUSES = {"queued", "running"}

DEUDOR_COPY_COLUMNS = (
    "codigo_entidad",
    "fecha_informacion",
    "tipo_identificacion",
    "numero_identificacion",
    "actividad",
    "situacion",
    "prestamos_total_garantias",
    "sin_uso",
    "garantias_otorgadas",
    "otros_conceptos",
    "garantias_preferidas_a",
    "garantias_preferidas_b",
    "sin_garantias_preferidas",
    "contragarantias_preferidas_a",
    "contragarantias_preferidas_b",
    "sin_contragarantias_preferidas",
    "previsiones",
    "deuda_cubierta",
    "proceso_judicial_revision",
    "refinanciaciones",
    "recategorizacion_obligatoria",
    "situacion_juridica",
    "irrecuperables_disposicion_tecnica",
    "dias_atraso",
    "nombre_entidad",
)

_job_creation_lock = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("No se pudo eliminar %s", path)


def _sanitize_copy_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _nullable_numeric(segment: str) -> str:
    value = segment.strip()
    if not value:
        return "\\N"
    return value.replace(",", ".")


def _required_integer(segment: str) -> str:
    value = segment.strip()
    return value or "0"


def _format_deudor_line(line: str, entidades_lookup: dict[str, str]) -> str:
    codigo_entidad = line[0:5].strip()
    nombre_entidad = entidades_lookup.get(codigo_entidad, "Desconocida")[:254]

    fields = (
        _sanitize_copy_text(codigo_entidad),
        _sanitize_copy_text(line[5:11].strip()),
        _sanitize_copy_text(line[11:13].strip()),
        _sanitize_copy_text(line[13:24].strip()),
        _sanitize_copy_text(line[24:27].strip()),
        _required_integer(line[27:29]),
        _nullable_numeric(line[29:41]),
        _nullable_numeric(line[41:53]),
        _nullable_numeric(line[53:65]),
        _nullable_numeric(line[65:77]),
        _nullable_numeric(line[77:89]),
        _nullable_numeric(line[89:101]),
        _nullable_numeric(line[101:113]),
        _nullable_numeric(line[113:125]),
        _nullable_numeric(line[125:137]),
        _nullable_numeric(line[137:149]),
        _nullable_numeric(line[149:161]),
        _required_integer(line[161:162]),
        _required_integer(line[162:163]),
        _required_integer(line[163:164]),
        _required_integer(line[164:165]),
        _required_integer(line[165:166]),
        _required_integer(line[166:167]),
        _required_integer(line[167:170]),
        _sanitize_copy_text(nombre_entidad),
    )
    return "\t".join(fields) + "\n"


def get_job_status_payload(job: ImportJob) -> dict[str, Any]:
    progress_percent = 0
    if job.progress_total:
        progress_percent = min(100, int((job.progress_current / job.progress_total) * 100))

    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "stage": job.stage,
        "message": job.message,
        "error": job.error,
        "processed_rows": int(job.processed_rows or 0),
        "progress_current": int(job.progress_current or 0),
        "progress_total": int(job.progress_total or 0),
        "progress_percent": progress_percent,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def mark_incomplete_jobs_as_failed() -> None:
    db = SessionLocal()
    try:
        interrupted_jobs = (
            db.query(ImportJob)
            .filter(ImportJob.job_type == JOB_TYPE_DEUDORES)
            .filter(ImportJob.status.in_(tuple(ACTIVE_JOB_STATUSES)))
            .all()
        )
        if not interrupted_jobs:
            return

        finished_at = _utc_now()
        for job in interrupted_jobs:
            job.status = "failed"
            job.stage = "interrupted"
            job.message = "El servicio se reinició antes de completar el job."
            job.error = "Job interrumpido por reinicio del servicio."
            job.finished_at = finished_at
        db.commit()
    finally:
        db.close()


def _save_upload_file(upload: UploadFile, destination: Path) -> None:
    upload.file.seek(0)
    with destination.open("wb") as output_file:
        while True:
            chunk = upload.file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            output_file.write(chunk)


def _validate_deudores_zip(zip_path: Path) -> None:
    try:
        with zipfile.ZipFile(zip_path) as zip_file:
            if DEUDORES_ZIP_MEMBER not in zip_file.namelist():
                raise HTTPException(
                    status_code=400,
                    detail="El archivo ZIP de deudores debe contener deudores.txt",
                )
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=400,
            detail="El archivo de deudores no es un ZIP válido.",
        ) from exc


def _ensure_no_active_job(db: Session) -> None:
    active_job = (
        db.query(ImportJob)
        .filter(ImportJob.job_type == JOB_TYPE_DEUDORES)
        .filter(ImportJob.status.in_(tuple(ACTIVE_JOB_STATUSES)))
        .order_by(ImportJob.created_at.desc())
        .first()
    )
    if active_job is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Ya hay un job de deudores activo ({active_job.id}). Esperá a que termine antes de iniciar otro.",
        )


def _upsert_entidades_batch(db: Session, batch: list[dict[str, str]]) -> None:
    if not batch:
        return

    statement = pg_insert(Entidad).values(batch)
    statement = statement.on_conflict_do_update(
        index_elements=[Entidad.codigo_entidad],
        set_={"nombre_entidad": statement.excluded.nombre_entidad},
    )
    db.execute(statement)
    db.commit()


def _process_entidades_file(entidades_path: Path, db: Session) -> int:
    processed_rows = 0
    batch: list[dict[str, str]] = []

    with entidades_path.open("rb") as entidades_file:
        for raw_line in entidades_file:
            line = raw_line.decode("ISO-8859-1").rstrip("\r\n")
            codigo_entidad = line[0:5].strip()
            if not codigo_entidad:
                continue

            batch.append(
                {
                    "codigo_entidad": codigo_entidad,
                    "nombre_entidad": line[5:].strip()[:70],
                }
            )
            processed_rows += 1

            if len(batch) >= 5_000:
                _upsert_entidades_batch(db, batch)
                batch.clear()

    if batch:
        _upsert_entidades_batch(db, batch)

    return processed_rows


def _load_entidades_lookup(db: Session) -> dict[str, str]:
    entidades = db.query(Entidad.codigo_entidad, Entidad.nombre_entidad).all()
    return {codigo: nombre for codigo, nombre in entidades}


def _update_job(job_id: str, **fields: Any) -> None:
    db = SessionLocal()
    try:
        job = db.get(ImportJob, job_id)
        if job is None:
            return
        for field_name, value in fields.items():
            setattr(job, field_name, value)
        db.commit()
    finally:
        db.close()


def _copy_deudores_to_postgres(
    deudores_zip_path: Path,
    entidades_lookup: dict[str, str],
    job_id: str,
) -> tuple[int, int]:
    connection = engine.raw_connection()
    cursor = connection.cursor()
    total_rows = 0
    processed_bytes = 0

    try:
        cursor.execute("SET statement_timeout TO 0")
        cursor.execute("SET synchronous_commit TO OFF")

        with zipfile.ZipFile(deudores_zip_path) as zip_file:
            zip_info = zip_file.getinfo(DEUDORES_ZIP_MEMBER)
            total_bytes = int(zip_info.file_size)
            _update_job(
                job_id,
                stage="processing_deudores",
                message="Cargando deudores en PostgreSQL con COPY...",
                progress_total=total_bytes,
                progress_current=0,
                processed_rows=0,
            )

            with zip_file.open(DEUDORES_ZIP_MEMBER) as deudores_txt:
                while True:
                    buffer = io.StringIO()
                    rows_in_batch = 0
                    write_line = buffer.write

                    while rows_in_batch < DEUDORES_COPY_BATCH_SIZE:
                        raw_line = deudores_txt.readline()
                        if not raw_line:
                            break
                        processed_bytes += len(raw_line)
                        total_rows += 1
                        rows_in_batch += 1
                        write_line(_format_deudor_line(raw_line.decode("ISO-8859-1"), entidades_lookup))

                    if rows_in_batch == 0:
                        break

                    buffer.seek(0)
                    try:
                        cursor.copy_from(
                            buffer,
                            Deudor.__tablename__,
                            sep="\t",
                            null="\\N",
                            columns=DEUDOR_COPY_COLUMNS,
                        )
                        connection.commit()
                    except Exception as exc:
                        connection.rollback()
                        raise RuntimeError(
                            f"Falló el COPY del lote de deudores alrededor de la fila {total_rows:,}".replace(",", ".")
                        ) from exc
                    finally:
                        buffer.close()

                    _update_job(
                        job_id,
                        progress_current=processed_bytes,
                        progress_total=total_bytes,
                        processed_rows=total_rows,
                        message=f"Procesadas {total_rows:,} filas de deudores.".replace(",", "."),
                    )
                    logger.info("COPY deudores: %s filas procesadas", f"{total_rows:,}".replace(",", "."))

            cursor.execute(f"ANALYZE {Deudor.__tablename__}")
            connection.commit()
            return total_rows, total_bytes
    finally:
        cursor.close()
        connection.close()


def _run_deudores_job(job_id: str, deudores_zip_path: Path, entidades_path: Path) -> None:
    db = SessionLocal()
    try:
        _update_job(
            job_id,
            status="running",
            stage="processing_entidades",
            message="Actualizando entidades...",
            started_at=_utc_now(),
        )

        entidades_actualizadas = _process_entidades_file(entidades_path, db)
        entidades_lookup = _load_entidades_lookup(db)
        logger.info("Entidades actualizadas: %s", entidades_actualizadas)
    except Exception as exc:
        db.rollback()
        logger.exception("Falló la actualización de entidades para el job %s", job_id)
        _update_job(
            job_id,
            status="failed",
            stage="failed",
            message="Falló la carga de entidades.",
            error=str(exc),
            finished_at=_utc_now(),
        )
        db.close()
        _safe_unlink(deudores_zip_path)
        _safe_unlink(entidades_path)
        return
    finally:
        db.close()

    try:
        processed_rows, total_bytes = _copy_deudores_to_postgres(deudores_zip_path, entidades_lookup, job_id)
        _update_job(
            job_id,
            status="completed",
            stage="completed",
            message=f"Importación completada. Se cargaron {processed_rows:,} filas.".replace(",", "."),
            processed_rows=processed_rows,
            progress_current=total_bytes,
            progress_total=total_bytes,
            finished_at=_utc_now(),
        )
    except Exception as exc:
        logger.exception("Falló la carga de deudores para el job %s", job_id)
        _update_job(
            job_id,
            status="failed",
            stage="failed",
            message="Falló la carga de deudores.",
            error=str(exc),
            finished_at=_utc_now(),
        )
    finally:
        _safe_unlink(deudores_zip_path)
        _safe_unlink(entidades_path)


def create_deudores_job(deudores: UploadFile, entidades: UploadFile) -> ImportJob:
    upload_prefix = uuid.uuid4().hex
    deudores_zip_path = UPLOAD_DIR / f"{upload_prefix}_deudores.zip"
    entidades_path = UPLOAD_DIR / f"{upload_prefix}_entidades.txt"

    with _job_creation_lock:
        db = SessionLocal()
        try:
            _ensure_no_active_job(db)
            _save_upload_file(deudores, deudores_zip_path)
            _save_upload_file(entidades, entidades_path)
            _validate_deudores_zip(deudores_zip_path)

            job = ImportJob(
                id=str(uuid.uuid4()),
                job_type=JOB_TYPE_DEUDORES,
                status="queued",
                stage="queued",
                message="Archivos recibidos. El job está en cola.",
                progress_current=0,
                progress_total=0,
                processed_rows=0,
                deudores_filename=deudores.filename,
                entidades_filename=entidades.filename,
                created_at=_utc_now(),
            )
            db.add(job)
            db.commit()
            db.refresh(job)
        except Exception:
            db.rollback()
            _safe_unlink(deudores_zip_path)
            _safe_unlink(entidades_path)
            raise
        finally:
            db.close()

    thread = threading.Thread(
        target=_run_deudores_job,
        args=(job.id, deudores_zip_path, entidades_path),
        daemon=True,
    )
    thread.start()
    return job
