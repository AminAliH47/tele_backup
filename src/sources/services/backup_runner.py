import os
import subprocess
import tempfile
import tarfile
import shutil
import logging
from typing import Tuple
from datetime import datetime
import docker
from sources import models
# from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class BackupError(Exception):
    pass


class BackupRunner:
    def __init__(
        self,
        source: models.Sources,
        output_format: str = 'tar.gz'
    ):
        self.source = source
        self.output_format = output_format
        self.temp_dir = None

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix='tele_backup_')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def create_backup(self) -> Tuple[str, int]:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if self.source.type == 'database':
            return self._backup_database(timestamp)
        elif self.source.type == 'volume':
            return self._backup_volume(timestamp)
        else:
            raise BackupError(f"Unsupported source type: {self.source.type}")

    def _backup_database(self, timestamp: str) -> Tuple[str, int]:
        match self.source.db_type:
            case 'postgresql':
                return self._backup_postgresql(timestamp)
            case 'mysql':
                return self._backup_mysql(timestamp)
            case 'sqlite':
                return self._backup_sqlite(timestamp)
            case _:
                raise BackupError(f"Unsupported database type: {self.source.db_type}")

    def _backup_postgresql(self, timestamp: str) -> Tuple[str, int]:
        logger.info(f"Starting PostgreSQL backup for {self.source.name}")

        base_filename = f"{self.source.name}_postgresql_{timestamp}"
        sql_file = os.path.join(self.temp_dir, f"{base_filename}.sql")

        # Build pg_dump command
        cmd = ['pg_dump']

        if self.source.db_host:
            cmd.extend(['-h', self.source.db_host])
        if self.source.db_port:
            cmd.extend(['-p', str(self.source.db_port)])
        if self.source.db_user:
            cmd.extend(['-U', self.source.db_user])

        cmd.extend([
            '--no-password',  # Use PGPASSWORD environment variable
            '--verbose',
            '--clean',
            '--if-exists',
            '--create',
            self.source.db_name
        ])

        # Set environment variables
        env = os.environ.copy()
        if self.source.db_password:
            env['PGPASSWORD'] = self.source.db_password

        try:
            with open(sql_file, 'w') as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True,
                    timeout=3600  # 1 hour timeout
                )

            if result.returncode != 0:
                raise BackupError(f"pg_dump failed: {result.stderr}")

            logger.info(f"PostgreSQL backup completed: {sql_file}")

            if self.output_format == 'tar.gz':
                return self._compress_to_tar(sql_file, base_filename)
            else:
                return self._finalize_sql_file(sql_file, base_filename)

        except subprocess.TimeoutExpired:
            raise BackupError("PostgreSQL backup timed out")
        except Exception as e:
            raise BackupError(f"PostgreSQL backup failed: {str(e)}")

    def _backup_mysql(self, timestamp: str) -> Tuple[str, int]:
        logger.info(f"Starting MySQL backup for {self.source.name}")

        base_filename = f"{self.source.name}_mysql_{timestamp}"
        sql_file = os.path.join(self.temp_dir, f"{base_filename}.sql")

        # Build mysqldump command
        cmd = ['mysqldump']

        if self.source.db_host:
            cmd.extend(['-h', self.source.db_host])
        if self.source.db_port:
            cmd.extend(['-P', str(self.source.db_port)])
        if self.source.db_user:
            cmd.extend(['-u', self.source.db_user])
        if self.source.db_password:
            cmd.extend([f'-p{self.source.db_password}'])

        cmd.extend([
            '--single-transaction',
            '--routines',
            '--triggers',
            '--add-drop-database',
            '--create-options',
            self.source.db_name
        ])

        try:
            with open(sql_file, 'w') as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=3600  # 1 hour timeout
                )

            if result.returncode != 0:
                raise BackupError(f"mysqldump failed: {result.stderr}")

            logger.info(f"MySQL backup completed: {sql_file}")

            if self.output_format == 'tar.gz':
                return self._compress_to_tar(sql_file, base_filename)
            else:
                return self._finalize_sql_file(sql_file, base_filename)

        except subprocess.TimeoutExpired:
            raise BackupError("MySQL backup timed out")
        except Exception as e:
            raise BackupError(f"MySQL backup failed: {str(e)}")

    def _backup_sqlite(self, timestamp: str) -> Tuple[str, int]:
        logger.info(f"Starting SQLite backup for {self.source.name}")

        base_filename = f"{self.source.name}_sqlite_{timestamp}"

        # For SQLite, we can either copy the file or use .backup command
        if self.source.db_host:  # If db_host is provided, treat as file path
            db_path = self.source.db_host
        else:
            db_path = self.source.db_name

        if not os.path.exists(db_path):
            raise BackupError(f"SQLite database file not found: {db_path}")

        try:
            if self.output_format == 'sql':
                # Use sqlite3 .dump command for SQL output
                sql_file = os.path.join(self.temp_dir, f"{base_filename}.sql")

                cmd = ['sqlite3', db_path, '.dump']
                with open(sql_file, 'w') as f:
                    result = subprocess.run(
                        cmd,
                        stdout=f,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=1800  # 30 minutes timeout
                    )

                if result.returncode != 0:
                    raise BackupError(f"sqlite3 dump failed: {result.stderr}")

                logger.info(f"SQLite backup completed: {sql_file}")
                return self._finalize_sql_file(sql_file, base_filename)
            else:
                # Copy the database file directly
                db_filename = os.path.basename(db_path)
                backup_file = os.path.join(self.temp_dir, f"{base_filename}_{db_filename}")
                shutil.copy2(db_path, backup_file)

                logger.info(f"SQLite backup completed: {backup_file}")
                return self._compress_to_tar(backup_file, base_filename)

        except subprocess.TimeoutExpired:
            raise BackupError("SQLite backup timed out")
        except Exception as e:
            raise BackupError(f"SQLite backup failed: {str(e)}")

    def _backup_volume(self, timestamp: str) -> Tuple[str, int]:
        logger.info(f"Starting Docker volume backup for {self.source.name}")

        base_filename = f"{self.source.name}_volume_{timestamp}"
        tar_file = os.path.join(self.temp_dir, f"{base_filename}.tar")

        try:
            client = docker.from_env()

            # Verify volume exists
            try:
                client.volumes.get(self.source.volume_name)
            except docker.errors.NotFound:
                raise BackupError(f"Docker volume '{self.source.volume_name}' not found")

            # Create a temporary container to access the volume
            container = client.containers.run(
                'alpine:latest',
                command='sleep 3600',
                volumes={self.source.volume_name: {'bind': '/data', 'mode': 'ro'}},
                detach=True,
                remove=True
            )

            try:
                # Create tar archive of volume contents
                archive_stream, _ = container.get_archive('/data')

                with open(tar_file, 'wb') as f:
                    for chunk in archive_stream:
                        f.write(chunk)

                logger.info(f"Docker volume backup completed: {tar_file}")

                if self.output_format == 'tar.gz':
                    return self._compress_to_tar(tar_file, base_filename)
                else:
                    # Even for SQL format, volumes are archived as tar
                    return self._compress_to_tar(tar_file, base_filename)

            finally:
                container.stop()

        except docker.errors.DockerException as e:
            raise BackupError(f"Docker volume backup failed: {str(e)}")
        except Exception as e:
            raise BackupError(f"Volume backup failed: {str(e)}")

    def _compress_to_tar(self, source_file: str, base_filename: str) -> Tuple[str, int]:
        tar_gz_file = os.path.join(self.temp_dir, f"{base_filename}.tar.gz")

        try:
            with tarfile.open(tar_gz_file, 'w:gz') as tar:
                tar.add(source_file, arcname=os.path.basename(source_file))

            file_size = os.path.getsize(tar_gz_file)
            logger.info(f"Created compressed archive: {tar_gz_file} ({file_size} bytes)")

            return tar_gz_file, file_size

        except Exception as e:
            raise BackupError(f"Compression failed: {str(e)}")

    def _finalize_sql_file(self, sql_file: str, base_filename: str) -> Tuple[str, int]:
        final_file = os.path.join(self.temp_dir, f"{base_filename}.sql")

        if sql_file != final_file:
            shutil.move(sql_file, final_file)

        file_size = os.path.getsize(final_file)
        logger.info(f"SQL backup finalized: {final_file} ({file_size} bytes)")

        return final_file, file_size


def create_backup(
    source: models.Sources,
    output_format: str = 'tar.gz'
) -> Tuple[str, int]:
    with BackupRunner(source, output_format) as runner:
        return runner.create_backup()
