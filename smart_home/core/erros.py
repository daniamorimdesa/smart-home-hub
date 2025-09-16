# smart_home/core/erros.py: exceções customizadas do hub
from __future__ import annotations
#--------------------------------------------------------------------------------------------------
# EXCEÇÕES CUSTOMIZADAS DO HUB  
#-------------------------------------------------------------------------------------------------- 
class SmartHomeError(Exception): ...


class DispositivoJaExiste(SmartHomeError): ...


class DispositivoNaoEncontrado(SmartHomeError): ...


class ComandoInvalido(SmartHomeError): ...


class AtributoInvalido(SmartHomeError): ...


class ConfigInvalida(SmartHomeError): ...


class ErroDeValidacao(SmartHomeError):
	"""Exceção para erros de validação de comandos, atributos ou rotinas."""
	def __init__(self, mensagem, detalhes=None):
		super().__init__(mensagem)
		self.detalhes = detalhes