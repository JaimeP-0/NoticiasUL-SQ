class ConfigSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigSingleton, cls).__new__(cls)
            cls._instance.config = {
                "APP_NAME": "Noticias Universitarias",
                "VERSION": "1.0",
                "DATABASE": "simulada.db"
            }
        return cls._instance
