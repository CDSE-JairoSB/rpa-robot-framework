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
            self._config = yaml.safe_load(f)

        logger.info(f"Configuración de entorno '{env_name}' cargada exitosamente.")
        return self._config

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
