__all__ = ["ZeusAgent", "__version__"]
__version__ = "2.1.0"


def __getattr__(name: str) -> object:
    if name == "ZeusAgent":
        from zeus_agent.library_runtime import ZeusAgent

        return ZeusAgent
    raise AttributeError(name)
