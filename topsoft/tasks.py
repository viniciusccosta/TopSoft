import logging
from time import sleep

from decouple import config

from topsoft.database import get_api_key, get_bilhetes_path, get_interval
from topsoft.utils import read_in_batches

logger = logging.getLogger(__name__)


def background_task(stop_event):
    def read_bilhetes_file(filepath):
        """
        Read the bilhetes file and return a list of dictionaries with the data.
        """

        logging.debug(f"Reading bilhetes file: {filepath}")

        bilhetes = []

        # TODO: TALVEZ será necessário um Banco de Dados
        # TODO: Forma mais inteligente de ler o arquivo sem precisar ler TODOS os dados toda vez
        # TODO: Como só registra hora:minuto podemos ler apenas a cada multiplo de 60 segundos (intervalo no frontend)

        for batch in read_in_batches(filepath):
            for tokens in batch:
                try:
                    bilhetes.append(
                        {
                            "marcação": tokens[
                                0
                            ],  # str(3) = 010 (Entrada) | 011 (Saída)
                            "date": tokens[1],  # dd/mm/yy ou dd/mm/yyyy
                            "time": tokens[2],  # hh:mm
                            "cartao": tokens[3],  # str(5) ou str(16)
                            "catraca": tokens[4],  # str(2) = 01, 02, 03, ..., 99
                            # "sequencial": tokens[5],  # str(10)
                        }
                    )
                except IndexError as e:
                    logging.warning(f"Error reading line")  # TODO: Melhorar mensagem
                    logging.exception(e)
                    continue

        return bilhetes

    def send_data_to_activitysoft(bilhetes):
        """
        Send data to ActivitySoft.
        """
        logging.debug(f"Sending data to ActivitySoft: {len(bilhetes)} bilhetes")

        api_key = get_api_key()
        if not api_key:
            logger.error("API key not found")
            return False

        # TODO: Implement the actual API call to ActivitySoft
        # TODO: Necessário saber quais dados já foram enviados pra evitar duplicados no ActSoft ?

        steps_api_debug = config("STEP_API_DEBUG", default=100)

        for i, bilhete in enumerate(bilhetes):
            try:
                if i % steps_api_debug == 0:
                    logger.debug(f"Sending bilhete {i} of {len(bilhetes)}")
                # TODO: Implement the API call here ASYNC
            except Exception as e:
                logger.warning(f"Error sending bilhete: {bilhete}")
                logger.exception(e)
                continue

        return True  # TODO: Simulating success

    def wait_for_interval(stop_event):
        """
        Wait for the specified interval.
        """

        intervalo = get_interval()

        for i in range(intervalo):
            if stop_event.is_set():
                logger.info("Stopping background task")
                return
            logger.debug(f"Waiting for {intervalo - i} seconds")
            sleep(1)

    # Log the start of the task
    logger.info("Starting background task")

    # Variables
    cnt = 1

    # Main loop
    while not stop_event.is_set():
        logger.info(f"Running background task {cnt}")
        cnt += 1

        try:
            # Ler arquivo:
            if bilhetes_path := get_bilhetes_path():
                data = read_bilhetes_file(bilhetes_path)

                # Enviar dados para ActivitySoft:
                result = send_data_to_activitysoft(data)
                if result:
                    logger.info("Data sent successfully")
                else:
                    logger.warning("Failed to send data")

                # TODO: Atualizar interface gráfica
        except Exception as e:
            logger.warning(f"Error na execução da tarefa")
            logger.exception(e)
        finally:
            wait_for_interval(stop_event)
