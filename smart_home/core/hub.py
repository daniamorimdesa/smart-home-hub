# # smart_home/core/hub.py: mantém dict de dispositivos, executa rotinas e delega comandos.
# # smart_home/core/hub.py (esqueleto)
# from typing import Dict
# from smart_home.core.dispositivos import DispositivoBase

# class Hub:
#     def __init__(self):
#         self.power_on: bool = False
#         self.dispositivos: Dict[str, DispositivoBase] = {}

#     def ligar_sistema(self):
#         self.power_on = True
#         # opcional: notificar observers
#         # opcional: chamar d.ligar() em cada dispositivo se fizer sentido

#     def desligar_sistema(self):
#         self.power_on = False
#         # opcional: notificar observers
#         # opcional: chamar d.desligar() em cada dispositivo se fizer sentido

#     def executar_comando(self, id_dispositivo: str, comando: str, **kwargs):
#         if not self.power_on:
#             # Bloqueia tudo quando o sistema está desligado
#             payload = {
#                 "id": id_dispositivo, "comando": comando,
#                 "bloqueado": True, "motivo": "sistema_desligado"
#             }
#             # enviar ao observer/logger (ComandoBloqueado)
#             # e informar na CLI
#             print("[BLOQUEADO] Sistema desligado.")
#             return

#         disp = self.dispositivos.get(id_dispositivo)
#         if not disp:
#             raise KeyError(f"Dispositivo '{id_dispositivo}' não encontrado.")
#         disp.executar_comando(comando, **kwargs)
