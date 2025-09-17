# smart_home/core/erros.py: exceções customizadas do hub
from __future__ import annotations
#--------------------------------------------------------------------------------------------------
# EXCEÇÕES CUSTOMIZADAS DO HUB  
#-------------------------------------------------------------------------------------------------- 
class SmartHomeError(Exception):
	"""Base para todas as exceções do Smart Home Hub.

	Aceita uma mensagem e um dict opcional de detalhes para diagnóstico.
	"""
	def __init__(self, mensagem: str, detalhes: dict | None = None) -> None:
		super().__init__(mensagem)
		self.detalhes = detalhes


class DispositivoJaExiste(SmartHomeError):
	"""Tentativa de criar/adicionar um dispositivo com ID já existente."""
	def __init__(self, mensagem: str, detalhes: dict | None = None) -> None:
		super().__init__(mensagem, detalhes)


class DispositivoNaoEncontrado(SmartHomeError):
	"""Dispositivo referenciado não foi localizado no hub."""
	def __init__(self, mensagem: str, detalhes: dict | None = None) -> None:
		super().__init__(mensagem, detalhes)


class ComandoInvalido(SmartHomeError):
	"""Comando não suportado pelo dispositivo ou inválido no contexto atual."""
	def __init__(self, mensagem: str, detalhes: dict | None = None) -> None:
		super().__init__(mensagem, detalhes)


class AtributoInvalido(SmartHomeError):
	"""Atributo inexistente ou valor fora do intervalo permitido."""
	def __init__(self, mensagem: str, detalhes: dict | None = None) -> None:
		super().__init__(mensagem, detalhes)


class ConfigInvalida(SmartHomeError):
	"""Erro de configuração (JSON inválido ou entrada malformada)."""
	def __init__(self, mensagem: str, detalhes: dict | None = None) -> None:
		super().__init__(mensagem, detalhes)


class ErroDeValidacao(SmartHomeError):
	"""Erros de validação de comandos, atributos ou rotinas."""
	def __init__(self, mensagem: str, detalhes: dict | None = None) -> None:
		super().__init__(mensagem, detalhes)


class RotinaNaoEncontrada(SmartHomeError):
	"""Rotina referenciada não foi localizada no hub."""
	def __init__(self, mensagem: str, detalhes: dict | None = None) -> None:
		super().__init__(mensagem, detalhes)