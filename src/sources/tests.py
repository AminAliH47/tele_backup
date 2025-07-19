import os
import tempfile
import shutil
import subprocess
import docker
from unittest.mock import patch, MagicMock, mock_open
from django.test import TestCase
from django.core.exceptions import ValidationError

from sources.models import Sources
from sources.services.backup_runner import BackupRunner, BackupError, create_backup


class BackupRunnerTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_db_source(self, db_type='postgresql'):
        return Sources.objects.create(
            name='Test Database',
            type='database',
            db_type=db_type,
            db_host='localhost',
            db_port=5432,
            db_name='testdb',
            db_user='testuser',
            db_password='testpass'
        )

    def _create_volume_source(self):
        return Sources.objects.create(
            name='Test Volume',
            type='volume',
            volume_name='test_volume'
        )


class PostgreSQLBackupTestCase(BackupRunnerTestCase):
    @patch('sources.services.backup_runner.subprocess.run')
    @patch('sources.services.backup_runner.tempfile.mkdtemp')
    @patch('sources.services.backup_runner.os.path.getsize')
    @patch('builtins.open', new_callable=mock_open)
    def test_postgresql_backup_success(self, mock_file, mock_getsize, mock_mkdtemp, mock_subprocess):
        mock_mkdtemp.return_value = self.temp_dir
        mock_subprocess.return_value = MagicMock(returncode=0, stderr='')
        mock_getsize.return_value = 1024

        source = self._create_db_source('postgresql')

        with BackupRunner(source, 'sql') as runner:
            runner.temp_dir = self.temp_dir
            file_path, file_size = runner._backup_postgresql('20240101_120000')

        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        cmd = call_args[0][0]

        self.assertIn('pg_dump', cmd)
        self.assertIn('-h', cmd)
        self.assertIn('localhost', cmd)
        self.assertIn('-p', cmd)
        self.assertIn('5432', cmd)
        self.assertIn('-U', cmd)
        self.assertIn('testuser', cmd)
        self.assertIn('testdb', cmd)

        env = call_args[1]['env']
        self.assertEqual(env['PGPASSWORD'], 'testpass')
        self.assertEqual(file_size, 1024)

    @patch('sources.services.backup_runner.subprocess.run')
    @patch('sources.services.backup_runner.tempfile.mkdtemp')
    def test_postgresql_backup_failure(self, mock_mkdtemp, mock_subprocess):
        mock_mkdtemp.return_value = self.temp_dir
        mock_subprocess.return_value = MagicMock(returncode=1, stderr='Connection failed')

        source = self._create_db_source('postgresql')

        with self.assertRaises(BackupError) as context:
            with BackupRunner(source, 'sql') as runner:
                runner.temp_dir = self.temp_dir
                runner._backup_postgresql('20240101_120000')

        self.assertIn('pg_dump failed', str(context.exception))

    @patch('sources.services.backup_runner.subprocess.run')
    @patch('sources.services.backup_runner.tempfile.mkdtemp')
    def test_postgresql_backup_timeout(self, mock_mkdtemp, mock_subprocess):
        mock_mkdtemp.return_value = self.temp_dir
        mock_subprocess.side_effect = subprocess.TimeoutExpired(['pg_dump'], 3600)

        source = self._create_db_source('postgresql')

        with self.assertRaises(BackupError) as context:
            with BackupRunner(source, 'sql') as runner:
                runner.temp_dir = self.temp_dir
                runner._backup_postgresql('20240101_120000')

        self.assertIn('timed out', str(context.exception))


class MySQLBackupTestCase(BackupRunnerTestCase):
    @patch('sources.services.backup_runner.subprocess.run')
    @patch('sources.services.backup_runner.tempfile.mkdtemp')
    @patch('sources.services.backup_runner.os.path.getsize')
    @patch('builtins.open', new_callable=mock_open)
    def test_mysql_backup_success(self, mock_file, mock_getsize, mock_mkdtemp, mock_subprocess):
        mock_mkdtemp.return_value = self.temp_dir
        mock_subprocess.return_value = MagicMock(returncode=0, stderr='')
        mock_getsize.return_value = 2048

        source = self._create_db_source('mysql')

        with BackupRunner(source, 'sql') as runner:
            runner.temp_dir = self.temp_dir
            file_path, file_size = runner._backup_mysql('20240101_120000')

        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        cmd = call_args[0][0]

        self.assertIn('mysqldump', cmd)
        self.assertIn('-h', cmd)
        self.assertIn('localhost', cmd)
        self.assertIn('-P', cmd)
        self.assertIn('5432', cmd)
        self.assertIn('-u', cmd)
        self.assertIn('testuser', cmd)
        self.assertIn('-ptestpass', cmd)
        self.assertIn('testdb', cmd)
        self.assertEqual(file_size, 2048)

    @patch('sources.services.backup_runner.subprocess.run')
    @patch('sources.services.backup_runner.tempfile.mkdtemp')
    def test_mysql_backup_failure(self, mock_mkdtemp, mock_subprocess):
        mock_mkdtemp.return_value = self.temp_dir
        mock_subprocess.return_value = MagicMock(returncode=1, stderr='Access denied')

        source = self._create_db_source('mysql')

        with self.assertRaises(BackupError) as context:
            with BackupRunner(source, 'sql') as runner:
                runner.temp_dir = self.temp_dir
                runner._backup_mysql('20240101_120000')

        self.assertIn('mysqldump failed', str(context.exception))


class SQLiteBackupTestCase(BackupRunnerTestCase):
    @patch('sources.services.backup_runner.subprocess.run')
    @patch('sources.services.backup_runner.tempfile.mkdtemp')
    @patch('sources.services.backup_runner.os.path.exists')
    @patch('sources.services.backup_runner.os.path.getsize')
    @patch('builtins.open', new_callable=mock_open)
    def test_sqlite_backup_sql_format(self, mock_file, mock_getsize, mock_exists, mock_mkdtemp, mock_subprocess):
        mock_mkdtemp.return_value = self.temp_dir
        mock_exists.return_value = True
        mock_subprocess.return_value = MagicMock(returncode=0, stderr='')
        mock_getsize.return_value = 512

        source = Sources.objects.create(
            name='Test SQLite',
            type='database',
            db_type='sqlite',
            db_name='/path/to/test.db'
        )

        with BackupRunner(source, 'sql') as runner:
            runner.temp_dir = self.temp_dir
            file_path, file_size = runner._backup_sqlite('20240101_120000')

        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        cmd = call_args[0][0]

        self.assertEqual(cmd, ['sqlite3', '/path/to/test.db', '.dump'])
        self.assertEqual(file_size, 512)

    @patch('sources.services.backup_runner.shutil.copy2')
    @patch('sources.services.backup_runner.tempfile.mkdtemp')
    @patch('sources.services.backup_runner.os.path.exists')
    def test_sqlite_backup_file_copy(self, mock_exists, mock_mkdtemp, mock_copy):
        mock_mkdtemp.return_value = self.temp_dir
        mock_exists.return_value = True

        source = Sources.objects.create(
            name='Test SQLite',
            type='database',
            db_type='sqlite',
            db_name='/path/to/test.db'
        )

        with patch('sources.services.backup_runner.tarfile.open') as mock_tarfile:
            mock_tar = MagicMock()
            mock_tarfile.return_value.__enter__ = MagicMock(return_value=mock_tar)
            mock_tarfile.return_value.__exit__ = MagicMock(return_value=None)

            with patch('sources.services.backup_runner.os.path.getsize', return_value=1024):
                with BackupRunner(source, 'tar.gz') as runner:
                    runner.temp_dir = self.temp_dir
                    file_path, file_size = runner._backup_sqlite('20240101_120000')

        mock_copy.assert_called_once()
        self.assertEqual(file_size, 1024)

    @patch('sources.services.backup_runner.os.path.exists')
    @patch('sources.services.backup_runner.tempfile.mkdtemp')
    def test_sqlite_backup_file_not_found(self, mock_mkdtemp, mock_exists):
        mock_mkdtemp.return_value = self.temp_dir
        mock_exists.return_value = False

        source = Sources.objects.create(
            name='Test SQLite',
            type='database',
            db_type='sqlite',
            db_name='/nonexistent/test.db'
        )

        with self.assertRaises(BackupError) as context:
            with BackupRunner(source, 'sql') as runner:
                runner.temp_dir = self.temp_dir
                runner._backup_sqlite('20240101_120000')

        self.assertIn('not found', str(context.exception))


class DockerVolumeBackupTestCase(BackupRunnerTestCase):
    @patch('sources.services.backup_runner.docker.from_env')
    @patch('sources.services.backup_runner.tempfile.mkdtemp')
    def test_volume_backup_success(self, mock_mkdtemp, mock_docker):
        mock_mkdtemp.return_value = self.temp_dir

        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        mock_volume = MagicMock()
        mock_client.volumes.get.return_value = mock_volume

        mock_container = MagicMock()
        mock_client.containers.run.return_value = mock_container
        mock_container.get_archive.return_value = (iter([b'test data']), None)

        source = self._create_volume_source()

        with patch('sources.services.backup_runner.tarfile.open') as mock_tarfile:
            mock_tar = MagicMock()
            mock_tarfile.return_value.__enter__ = MagicMock(return_value=mock_tar)
            mock_tarfile.return_value.__exit__ = MagicMock(return_value=None)

            with patch('sources.services.backup_runner.os.path.getsize', return_value=2048):
                with BackupRunner(source, 'tar.gz') as runner:
                    runner.temp_dir = self.temp_dir
                    file_path, file_size = runner._backup_volume('20240101_120000')

        mock_client.volumes.get.assert_called_once_with('test_volume')
        mock_client.containers.run.assert_called_once()
        mock_container.get_archive.assert_called_once_with('/data')
        mock_container.stop.assert_called_once()
        self.assertEqual(file_size, 2048)

    @patch('sources.services.backup_runner.docker.from_env')
    @patch('sources.services.backup_runner.tempfile.mkdtemp')
    def test_volume_backup_volume_not_found(self, mock_mkdtemp, mock_docker):
        mock_mkdtemp.return_value = self.temp_dir

        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_client.volumes.get.side_effect = docker.errors.NotFound('Volume not found')

        source = self._create_volume_source()

        with self.assertRaises(BackupError) as context:
            with BackupRunner(source, 'tar.gz') as runner:
                runner.temp_dir = self.temp_dir
                runner._backup_volume('20240101_120000')

        self.assertIn('not found', str(context.exception))


class BackupRunnerIntegrationTestCase(BackupRunnerTestCase):
    def test_unsupported_source_type(self):
        source = Sources(name='Test', type='unsupported')

        with self.assertRaises(BackupError) as context:
            with BackupRunner(source) as runner:
                runner.create_backup()

        self.assertIn('Unsupported source type', str(context.exception))

    def test_unsupported_database_type(self):
        source = Sources(name='Test', type='database', db_type='mongodb')

        with self.assertRaises(BackupError) as context:
            with BackupRunner(source) as runner:
                runner._backup_database('timestamp')

        self.assertIn('Unsupported database type', str(context.exception))

    @patch('sources.services.backup_runner.tarfile.open')
    @patch('sources.services.backup_runner.os.path.getsize')
    def test_compression_success(self, mock_getsize, mock_tarfile):
        mock_getsize.return_value = 1024
        mock_tar = MagicMock()
        mock_tarfile.return_value.__enter__ = MagicMock(return_value=mock_tar)
        mock_tarfile.return_value.__exit__ = MagicMock(return_value=None)

        source = Sources(name='Test')

        with BackupRunner(source) as runner:
            runner.temp_dir = self.temp_dir
            test_file = os.path.join(self.temp_dir, 'test.sql')
            with open(test_file, 'w') as f:
                f.write('test content')

            file_path, file_size = runner._compress_to_tar(test_file, 'test_backup')

        self.assertEqual(file_size, 1024)
        mock_tar.add.assert_called_once()

    def test_context_manager_cleanup(self):
        source = Sources(name='Test')
        temp_dir = None

        with BackupRunner(source) as runner:
            temp_dir = runner.temp_dir
            self.assertTrue(os.path.exists(temp_dir))

        self.assertFalse(os.path.exists(temp_dir))

    @patch('sources.services.backup_runner.BackupRunner.create_backup')
    def test_create_backup_function(self, mock_create_backup):
        mock_create_backup.return_value = ('/path/to/backup.tar.gz', 2048)

        source = Sources(name='Test')
        file_path, file_size = create_backup(source, 'tar.gz')

        self.assertEqual(file_path, '/path/to/backup.tar.gz')
        self.assertEqual(file_size, 2048)


class SourcesModelTestCase(TestCase):
    def test_database_source_validation(self):
        source = Sources(
            name='Test DB',
            type='database',
            db_name='testdb'
        )

        with self.assertRaises(ValidationError) as context:
            source.clean()

        self.assertIn('Database type is required', str(context.exception))

    def test_volume_source_validation(self):
        source = Sources(
            name='Test Volume',
            type='volume'
        )

        with self.assertRaises(ValidationError) as context:
            source.clean()

        self.assertIn('Volume name is required', str(context.exception))

    def test_valid_database_source(self):
        source = Sources(
            name='Test DB',
            type='database',
            db_type='postgresql',
            db_name='testdb'
        )

        try:
            source.clean()
        except ValidationError:
            self.fail("ValidationError raised for valid database source")

    def test_valid_volume_source(self):
        source = Sources(
            name='Test Volume',
            type='volume',
            volume_name='test_volume'
        )

        try:
            source.clean()
        except ValidationError:
            self.fail("ValidationError raised for valid volume source")
