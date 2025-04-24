import logging
from time import sleep

from topsoft.database import get_api_key, get_bilhetes_path, get_interval

logger = logging.getLogger(__name__)


def background_task(stop_event):
    def read_bilhetes_file(filepath):
        """
        Read the bilhetes file and return a list of dictionaries with the data.
        """
        with open(filepath, "r") as f:
            data = f.readlines()

        # TODO: Process the data as needed ?

        return data

    def send_data_to_activitysoft(data):
        """
        Send data to ActivitySoft.
        """
        logging.debug(f"Sending data to ActivitySoft: {data}")

        api_key = get_api_key()

    # Log the start of the task
    logger.info("Starting background task")

    # Variables
    intervalo = get_interval()
    cnt = 1

    # Main loop
    while True:
        logger.info(f"Running background task {cnt}")
        cnt += 1

        # Ler arquivo (conforme configuração)
        try:
            data = read_bilhetes_file(get_bilhetes_path())
        except Exception as e:
            logger.error(f"Error reading bilhetes file: {e}")
            logger.exception(e)
            continue

        # Enviar dados para ActivitySoft
        try:
            result = send_data_to_activitysoft(data)
            if result:
                logger.info("Data sent successfully")
            else:
                logger.error("Failed to send data")
        except Exception as e:
            logger.error(f"Error sending data to ActivitySoft: {e}")
            logger.exception(e)

        # TODO: Atualizar interface gráfica

        # Wait for the next interval
        for i in range(intervalo):
            if stop_event.is_set():
                logger.info("Stopping background task")
                return
            logger.debug(f"Waiting for {intervalo - i} seconds")
            sleep(1)
