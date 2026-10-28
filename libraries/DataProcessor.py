import os
import yaml
from typing import Any, Dict
from robot.api import logger


class DataProcessor:
    """Librería personalizada para procesamiento de datos, configuración y utilidades RPA."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self):
        self._config: Dict[str, Any] = {}

    def load_environment_config(self, env_name: str, config_dir: str = "config") -> Dict[str, Any]:
        """Carga la configuración según el entorno especificado (dev, uat, prod).
        
        Args:
            env_name: Nombre del entorno ('dev', 'uat', 'prod').
            config_dir: Ruta relativa al directorio de configuraciones.
            
        Returns:
            Diccionario con la configuración del entorno.
        """
        config_file = os.path.join(config_dir, f"{env_name.lower()}.yaml")
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"El archivo de configuración para '{env_name}' no existe en: {config_file}")

        with open(config_file, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}

        local_config = self.load_local_config()
        if local_config:
            self._config = self._deep_merge(self._config, local_config)
            logger.info("Se aplicó config/local.yaml sobre el entorno (archivo no versionado).")

        logger.info(f"Configuración de entorno '{env_name}' cargada exitosamente.")
        return self._config

    def load_local_config(self, config_file: str = "config/local.yaml") -> Dict[str, Any]:
        """Carga overrides locales gitignorados. Si no existe, retorna un dict vacío."""
        if not os.path.exists(config_file):
            logger.info(f"Sin configuración local en '{config_file}'.")
            return {}

        with open(config_file, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}

        if not isinstance(loaded, dict):
            raise ValueError(f"El archivo '{config_file}' debe contener un mapeo YAML.")
        logger.info(f"Configuración local cargada desde '{config_file}'.")
        return loaded

    def resolve_runtime_value(
        self,
        cli_value: Any = "",
        env_name: str = "",
        local_config: Any = None,
        local_key: str = "",
        default: Any = "",
    ) -> str:
        """Resuelve un parámetro: CLI > variable de entorno > config local > default."""
        local_value = self._nested_get(local_config or {}, local_key)
        env_value = os.environ.get(env_name, "") if env_name else ""
        return self._first_non_empty(cli_value, env_value, local_value, default)

    def default_chrome_profile_path(self, profile_name: str = "Default") -> str:
        """Elige un perfil Chrome usable: copia local del proyecto, o la ruta estándar según el SO."""
        local_path = os.path.abspath(os.path.join("data", "chrome-profile", profile_name))
        if self._is_readable_dir(local_path):
            return local_path

        candidates = [
            # macOS
            os.path.join(
                os.path.expanduser("~"),
                "Library",
                "Application Support",
                "Google",
                "Chrome",
                profile_name,
            ),
            # Linux (standard chrome and chromium paths)
            os.path.join(os.path.expanduser("~"), ".config", "google-chrome", profile_name),
            os.path.join(os.path.expanduser("~"), ".config", "chromium", profile_name),
            # Windows
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data", profile_name),
        ]
        for candidate in candidates:
            if candidate and self._is_readable_dir(candidate):
                return candidate
        if os.path.isdir(local_path):
            return local_path
        for candidate in candidates:
            if candidate and os.path.isdir(candidate):
                return candidate
        return ""

    def resolve_chrome_binary_path(self, cli_override: str = "") -> str:
        """Resuelve el binario ejecutable de Chrome o Chromium (macOS, Linux, Windows).

        Orden de resolución:
        1. cli_override (CLI o variable de Robot Framework si existe)
        2. Variables de entorno: CHROME_BINARY_PATH, CHROME_BIN, GOOGLE_CHROME_BIN
        3. Búsqueda en PATH de ejecutables conocidos (google-chrome, chromium, etc.)
        4. Rutas estándar del sistema operativo
        """
        import shutil
        import sys

        override = (cli_override or "").strip()
        if override and (os.path.exists(override) or shutil.which(override)):
            return override

        for env_var in ("CHROME_BINARY_PATH", "CHROME_BIN", "GOOGLE_CHROME_BIN"):
            val = os.environ.get(env_var, "").strip()
            if val and (os.path.exists(val) or shutil.which(val)):
                return val

        for binary_name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
            found = shutil.which(binary_name)
            if found:
                return found

        mac_binary = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(mac_binary):
            return mac_binary

        linux_candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
        for path in linux_candidates:
            if os.path.exists(path):
                return path

        win_candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for path in win_candidates:
            if os.path.exists(path):
                return path

        if sys.platform == "darwin":
            return mac_binary
        return "google-chrome"

    def copy_chrome_user_data(self, profile_path: str, profile_name: str, destination_root: str) -> str:
        """Copia el perfil a un user-data-dir temporal. Local State es opcional si macOS lo bloquea."""
        import shutil

        profile_path = os.path.abspath(profile_path)
        parent_path, path_tail = os.path.split(profile_path.rstrip(os.sep))
        if path_tail != profile_name:
            raise ValueError(f"The profile path must end with '{profile_name}'.")

        lock_path = os.path.join(parent_path, "SingletonLock")
        if os.path.exists(lock_path):
            raise RuntimeError(
                "[SYSTEM_EXCEPTION] The source Chrome profile is in use. Close all Google Chrome windows first."
            )

        os.makedirs(destination_root, exist_ok=True)
        source_local_state = os.path.join(parent_path, "Local State")
        source_profile = os.path.join(parent_path, profile_name)
        ignore_names = {
            "SingletonLock",
            "SingletonCookie",
            "SingletonSocket",
            "RunningChromeVersion",
            "DevToolsActivePort",
        }

        try:
            if os.path.isfile(source_local_state):
                shutil.copy2(source_local_state, os.path.join(destination_root, "Local State"))
        except PermissionError:
            logger.warn(
                "macOS bloqueó la lectura de 'Local State' (TCC). Se continúa sin ese archivo."
            )

        try:
            shutil.copytree(
                source_profile,
                os.path.join(destination_root, profile_name),
                ignore=lambda _dir, names: [name for name in names if name in ignore_names],
            )
        except PermissionError as exc:
            raise PermissionError(
                "[SYSTEM_EXCEPTION] macOS bloqueó la lectura del perfil de Chrome "
                f"({source_profile}). Ejecuta el robot desde Terminal.app, concede "
                "Acceso Completo al Disco a la app que lanza robot, o copia el perfil "
                "con scripts/seed_chrome_profile.sh hacia data/chrome-profile/."
            ) from exc

        logger.info(f"Perfil Chrome copiado a '{destination_root}'.")
        return destination_root

    def _is_readable_dir(self, path: str) -> bool:
        if not path or not os.path.isdir(path):
            return False
        try:
            os.listdir(path)
            return True
        except PermissionError:
            return False

    def _first_non_empty(self, *values: Any) -> str:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text and text not in {"${EMPTY}", "${None}", "None", "undefined"}:
                return text
        return ""

    def _nested_get(self, data: Any, dotted_key: str) -> str:
        if not dotted_key or not isinstance(data, dict):
            return ""
        current: Any = data
        for part in dotted_key.split("."):
            if not isinstance(current, dict) or part not in current:
                return ""
            current = current[part]
        if current is None:
            return ""
        return str(current).strip()

    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)
        for key, value in overlay.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            elif self._first_non_empty(value):
                merged[key] = value
        return merged

    def load_locators(self, locator_file: str = "resources/locators/portal_locators.yaml") -> Dict[str, Any]:
        """Carga el diccionario de selectores desde un archivo YAML centralizado.
        
        Args:
            locator_file: Ruta al archivo YAML de localizadores.
            
        Returns:
            Diccionario anidado con los localizadores.
        """
        if not os.path.exists(locator_file):
            raise FileNotFoundError(f"El archivo de localizadores no existe en: {locator_file}")

        with open(locator_file, "r", encoding="utf-8") as f:
            locators = yaml.safe_load(f)

        logger.info("Localizadores UI cargados correctamente.")
        return locators

    def validate_transaction_data(self, record: Dict[str, Any]) -> bool:
        """Aplica reglas de negocio para validar la consistencia de un registro transaccional.
        
        Args:
            record: Diccionario con los datos del ítem a procesar.
            
        Returns:
            True si es válido, lanza excepción de negocio si falta algún dato crítico.
        """
        required_fields = ["OrderNumber", "Head", "Body", "Legs", "Address"]
        for field in required_fields:
            if field not in record or not str(record[field]).strip():
                raise ValueError(f"[BUSINESS_EXCEPTION] El campo requerido '{field}' está vacío o ausente en el ítem.")

        logger.info(f"Registro '{record.get('OrderNumber')}' validado según reglas de negocio.")
        return True

    def mask_sensitive_data(self, value: str, visible_chars: int = 4) -> str:
        """Enmascara datos sensibles para logs respetando políticas de privacidad.
        
        Args:
            value: Cadena con información sensible (tarjeta, token, identificación).
            visible_chars: Cantidad de caracteres visibles al final.
            
        Returns:
            Cadena enmascarada (ej. '************1234').
        """
        if not value:
            return ""
        str_val = str(value)
        if len(str_val) <= visible_chars:
            return "*" * len(str_val)
        return "*" * (len(str_val) - visible_chars) + str_val[-visible_chars:]
