import logging
from time import sleep

logger = logging.getLogger(__name__)


def background_task(intervalo=60):
    cnt = 0

    while True:
        logger.info(f"Running background task {cnt}")
        cnt += 1

        # TODO: Ler arquivo (conforme configuração)
        # TODO: Enviar dados para ActivitySoft
        # TODO: Atualizar interface gráfica

        # TODO: Aguardar intervalo
        sleep(intervalo)
