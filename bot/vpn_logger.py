import logging
from config.config import DEBUG_VPN

class VPNLogger:
    """
    Специальный logger для VPN операций с возможностью отключения
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.enabled = DEBUG_VPN
        
        if self.enabled and not self.logger.handlers:
            # Настраиваем logger только если включен DEBUG_VPN
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def info(self, message: str):
        """Логирует INFO сообщение если включен DEBUG_VPN"""
        if self.enabled:
            self.logger.info(message)
    
    def warning(self, message: str):
        """Логирует WARNING сообщение если включен DEBUG_VPN"""
        if self.enabled:
            self.logger.warning(message)
    
    def error(self, message: str):
        """Логирует ERROR сообщение (всегда активно для важных ошибок)"""
        # Ошибки логируем всегда, даже если DEBUG_VPN выключен
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.ERROR)
        self.logger.error(message)
    
    def exception(self, message: str):
        """Логирует исключение с трейсом (всегда активно для важных ошибок)"""
        # Исключения логируем всегда
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.ERROR)
        self.logger.exception(message)
    
    def debug(self, message: str):
        """Логирует DEBUG сообщение если включен DEBUG_VPN"""
        if self.enabled:
            self.logger.debug(message)


# Создаем экземпляры для разных модулей
vpn_manager_logger = VPNLogger("vpn_manager")
vpn_api_logger = VPNLogger("vpn_api") 