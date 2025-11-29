"""
Comprehensive environment setup verification tests.

These tests are designed to FAIL if the environment is not properly configured.
Following TDD principles: write tests first, then fix the setup to make them pass.

CRITICAL: Never modify these tests. Always fix the setup/code to make tests pass.
"""

import sys
import os
import subprocess
import importlib.util
from pathlib import Path


class TestDjangoInstallation:
    """Test Django is properly installed and importable."""
    
    def test_django_is_installed(self):
        """Django must be installed in the virtual environment."""
        try:
            import django
        except ImportError as e:
            raise AssertionError(
                f"Django is not installed. ImportError: {e}. "
                "Run: pip install Django"
            )
    
    def test_django_version_is_recent(self):
        """Django version should be 4.x or higher."""
        import django
        major_version = int(django.VERSION[0])
        assert major_version >= 4, (
            f"Django version {django.get_version()} is too old. "
            f"Expected version 4.x or higher. Run: pip install --upgrade Django"
        )
    
    def test_django_can_be_imported_from_command_line(self):
        """Django should be importable from command line Python."""
        result = subprocess.run(
            [sys.executable, "-c", "import django; print(django.get_version())"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, (
            f"Failed to import Django from command line. "
            f"Error: {result.stderr}"
        )
        assert result.stdout.strip(), "Django version output is empty"


class TestRequiredPackages:
    """Test all required packages are installed."""
    
    def test_mysqlclient_is_installed(self):
        """mysqlclient must be installed for MySQL database support."""
        try:
            import MySQLdb
        except ImportError as e:
            raise AssertionError(
                f"mysqlclient is not installed. ImportError: {e}. "
                "Run: pip install mysqlclient"
            )
    
    def test_pillow_is_installed(self):
        """Pillow must be installed for image handling."""
        try:
            from PIL import Image
        except ImportError as e:
            raise AssertionError(
                f"Pillow is not installed. ImportError: {e}. "
                "Run: pip install Pillow"
            )
    
    def test_djangorestframework_is_installed(self):
        """Django REST framework must be installed."""
        try:
            import rest_framework
        except ImportError as e:
            raise AssertionError(
                f"djangorestframework is not installed. ImportError: {e}. "
                "Run: pip install djangorestframework"
            )
    
    def test_django_cors_headers_is_installed(self):
        """django-cors-headers must be installed."""
        try:
            import corsheaders
        except ImportError as e:
            raise AssertionError(
                f"django-cors-headers is not installed. ImportError: {e}. "
                "Run: pip install django-cors-headers"
            )
    
    def test_all_packages_importable(self):
        """All required packages must be importable without errors."""
        required_packages = {
            'django': 'Django',
            'MySQLdb': 'mysqlclient',
            'PIL': 'Pillow',
            'rest_framework': 'djangorestframework',
            'corsheaders': 'django-cors-headers'
        }
        
        failed_imports = []
        for module_name, package_name in required_packages.items():
            try:
                __import__(module_name)
            except ImportError:
                failed_imports.append(package_name)
        
        assert not failed_imports, (
            f"Failed to import packages: {', '.join(failed_imports)}. "
            f"Run: pip install {' '.join(failed_imports)}"
        )


class TestDjangoProjectStructure:
    """Test Django project structure exists with correct naming."""
    
    @property
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent
    
    def test_manage_py_exists(self):
        """manage.py must exist in project root."""
        manage_py = self.project_root / "manage.py"
        assert manage_py.exists(), (
            f"manage.py not found at {manage_py}. "
            "Run: django-admin startproject student_moving_marketplace ."
        )
        assert manage_py.is_file(), "manage.py exists but is not a file"
    
    def test_manage_py_is_executable(self):
        """manage.py should be executable."""
        manage_py = self.project_root / "manage.py"
        if manage_py.exists():
            assert os.access(manage_py, os.X_OK), (
                f"manage.py is not executable. Run: chmod +x manage.py"
            )
    
    def test_project_directory_exists(self):
        """student_moving_marketplace project directory must exist."""
        project_dir = self.project_root / "student_moving_marketplace"
        assert project_dir.exists(), (
            f"Project directory {project_dir} not found. "
            "Run: django-admin startproject student_moving_marketplace ."
        )
        assert project_dir.is_dir(), (
            "student_moving_marketplace exists but is not a directory"
        )
    
    def test_project_settings_exists(self):
        """settings.py must exist in project directory."""
        settings_py = self.project_root / "student_moving_marketplace" / "settings.py"
        assert settings_py.exists(), (
            f"settings.py not found at {settings_py}. "
            "Run: django-admin startproject student_moving_marketplace ."
        )
    
    def test_project_urls_exists(self):
        """urls.py must exist in project directory."""
        urls_py = self.project_root / "student_moving_marketplace" / "urls.py"
        assert urls_py.exists(), (
            f"urls.py not found at {urls_py}. "
            "Project structure is incomplete."
        )
    
    def test_project_wsgi_exists(self):
        """wsgi.py must exist in project directory."""
        wsgi_py = self.project_root / "student_moving_marketplace" / "wsgi.py"
        assert wsgi_py.exists(), (
            f"wsgi.py not found at {wsgi_py}. "
            "Project structure is incomplete."
        )
    
    def test_project_asgi_exists(self):
        """asgi.py must exist in project directory."""
        asgi_py = self.project_root / "student_moving_marketplace" / "asgi.py"
        assert asgi_py.exists(), (
            f"asgi.py not found at {asgi_py}. "
            "Project structure is incomplete."
        )
    
    def test_core_app_exists(self):
        """core app directory must exist."""
        core_dir = self.project_root / "core"
        assert core_dir.exists(), (
            f"Core app directory {core_dir} not found. "
            "Run: python manage.py startapp core"
        )
        assert core_dir.is_dir(), "core exists but is not a directory"
    
    def test_core_app_has_models(self):
        """core app must have models.py."""
        models_py = self.project_root / "core" / "models.py"
        assert models_py.exists(), (
            f"models.py not found in core app at {models_py}. "
            "Run: python manage.py startapp core"
        )
    
    def test_core_app_has_views(self):
        """core app must have views.py."""
        views_py = self.project_root / "core" / "views.py"
        assert views_py.exists(), (
            f"views.py not found in core app at {views_py}. "
            "Run: python manage.py startapp core"
        )
    
    def test_core_app_has_apps_config(self):
        """core app must have apps.py with proper configuration."""
        apps_py = self.project_root / "core" / "apps.py"
        assert apps_py.exists(), (
            f"apps.py not found in core app at {apps_py}. "
            "Run: python manage.py startapp core"
        )
    
    def test_core_app_has_admin(self):
        """core app must have admin.py."""
        admin_py = self.project_root / "core" / "admin.py"
        assert admin_py.exists(), (
            f"admin.py not found in core app at {admin_py}. "
            "Run: python manage.py startapp core"
        )
    
    def test_core_app_has_tests(self):
        """core app must have tests.py."""
        tests_py = self.project_root / "core" / "tests.py"
        assert tests_py.exists(), (
            f"tests.py not found in core app at {tests_py}. "
            "Core app structure is incomplete."
        )
    
    def test_django_project_name_is_correct(self):
        """Django project must be named 'student_moving_marketplace'."""
        settings_py = self.project_root / "student_moving_marketplace" / "settings.py"
        if settings_py.exists():
            content = settings_py.read_text()
            assert "student_moving_marketplace" in content, (
                "Project name in settings.py does not match 'student_moving_marketplace'"
            )


class TestVirtualEnvironmentIsolation:
    """Test virtual environment is properly isolated from system Python."""
    
    def test_python_executable_is_in_virtualenv(self):
        """Python executable must be from the virtual environment, not system."""
        python_path = sys.executable
        assert "student_moving_env" in python_path, (
            f"Python executable is not from student_moving_env. "
            f"Current: {python_path}. "
            "Activate the virtual environment: pyenv activate student_moving_env"
        )
    
    def test_virtualenv_is_active(self):
        """Virtual environment must be active."""
        virtual_env = os.environ.get('VIRTUAL_ENV') or os.environ.get('PYENV_VIRTUAL_ENV')
        assert virtual_env is not None, (
            "No virtual environment is active. "
            "Run: pyenv activate student_moving_env"
        )
        assert "student_moving_env" in virtual_env, (
            f"Wrong virtual environment is active: {virtual_env}. "
            "Run: pyenv activate student_moving_env"
        )
    
    def test_pip_installs_to_virtualenv(self):
        """pip must install packages to virtual environment, not system."""
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "pip"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "Failed to run pip show pip"
        assert "student_moving_env" in result.stdout, (
            f"pip is not using the virtual environment. "
            f"pip location: {result.stdout}"
        )
    
    def test_site_packages_is_in_virtualenv(self):
        """Site-packages directory must be in virtual environment."""
        import site
        site_packages = site.getsitepackages()
        virtualenv_site_packages = [
            path for path in site_packages 
            if "student_moving_env" in path
        ]
        assert virtualenv_site_packages, (
            f"No site-packages directory found in student_moving_env. "
            f"Site packages: {site_packages}"
        )
    
    def test_no_system_python_packages_in_path(self):
        """System Python packages should not be in sys.path (proper isolation)."""
        # This is a warning test - we want to ensure isolation
        system_paths = [
            path for path in sys.path 
            if "/usr/lib/python" in path or "/Library/Python" in path
        ]
        # We allow system paths but they should come after virtualenv paths
        if system_paths:
            virtualenv_paths = [
                path for path in sys.path 
                if "student_moving_env" in path
            ]
            assert virtualenv_paths, (
                "System Python paths found but no virtualenv paths. "
                "Virtual environment may not be properly activated."
            )


class TestRequirementsTxt:
    """Test requirements.txt exists and is properly formatted."""
    
    @property
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent
    
    def test_requirements_txt_exists(self):
        """requirements.txt must exist in project root."""
        requirements_txt = self.project_root / "requirements.txt"
        assert requirements_txt.exists(), (
            f"requirements.txt not found at {requirements_txt}. "
            "Create requirements.txt with all required packages."
        )
    
    def test_requirements_txt_is_not_empty(self):
        """requirements.txt must not be empty."""
        requirements_txt = self.project_root / "requirements.txt"
        if requirements_txt.exists():
            content = requirements_txt.read_text().strip()
            assert content, "requirements.txt is empty"
    
    def test_requirements_contains_django(self):
        """requirements.txt must include Django."""
        requirements_txt = self.project_root / "requirements.txt"
        if requirements_txt.exists():
            content = requirements_txt.read_text().lower()
            assert "django" in content, (
                "requirements.txt does not include Django"
            )
    
    def test_requirements_contains_mysqlclient(self):
        """requirements.txt must include mysqlclient."""
        requirements_txt = self.project_root / "requirements.txt"
        if requirements_txt.exists():
            content = requirements_txt.read_text().lower()
            assert "mysqlclient" in content, (
                "requirements.txt does not include mysqlclient"
            )
    
    def test_requirements_contains_pillow(self):
        """requirements.txt must include Pillow."""
        requirements_txt = self.project_root / "requirements.txt"
        if requirements_txt.exists():
            content = requirements_txt.read_text().lower()
            assert "pillow" in content, (
                "requirements.txt does not include Pillow"
            )
    
    def test_requirements_contains_djangorestframework(self):
        """requirements.txt must include djangorestframework."""
        requirements_txt = self.project_root / "requirements.txt"
        if requirements_txt.exists():
            content = requirements_txt.read_text().lower()
            assert "djangorestframework" in content, (
                "requirements.txt does not include djangorestframework"
            )
    
    def test_requirements_contains_django_cors_headers(self):
        """requirements.txt must include django-cors-headers."""
        requirements_txt = self.project_root / "requirements.txt"
        if requirements_txt.exists():
            content = requirements_txt.read_text().lower()
            assert "django-cors-headers" in content, (
                "requirements.txt does not include django-cors-headers"
            )
    
    def test_all_requirements_are_installed(self):
        """All packages in requirements.txt must be installed."""
        requirements_txt = self.project_root / "requirements.txt"
        if requirements_txt.exists():
            result = subprocess.run(
                [sys.executable, "-m", "pip", "check"],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, (
                f"pip check failed. Dependency issues detected:\n{result.stdout}"
            )


class TestDjangoProjectFunctionality:
    """Test Django project is functional and can run basic commands."""
    
    @property
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent
    
    def test_django_check_passes(self):
        """Django system check must pass without errors."""
        manage_py = self.project_root / "manage.py"
        if manage_py.exists():
            result = subprocess.run(
                [sys.executable, str(manage_py), "check"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            assert result.returncode == 0, (
                f"Django check failed:\n{result.stdout}\n{result.stderr}"
            )
    
    def test_can_import_settings(self):
        """Django settings must be importable."""
        # Add project to path temporarily
        project_root = str(self.project_root)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        try:
            import student_moving_marketplace.settings
        except ImportError as e:
            raise AssertionError(
                f"Failed to import settings: {e}. "
                "Django project may not be properly configured."
            )
    
    def test_secret_key_exists_in_settings(self):
        """SECRET_KEY must be defined in settings."""
        project_root = str(self.project_root)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        try:
            from student_moving_marketplace import settings
            assert hasattr(settings, 'SECRET_KEY'), (
                "SECRET_KEY not found in settings.py"
            )
            assert settings.SECRET_KEY, "SECRET_KEY is empty"
        except ImportError:
            # Skip if settings can't be imported (will be caught by other test)
            pass
