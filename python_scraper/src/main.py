import logging

import mysql.connector

from src.scraper import run_scraper

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Inizializzazione Opis Manager Scraper...")

    try:
        run_scraper()
        logger.info("Estrazione dati completata con successo.")

    except KeyboardInterrupt:
        logger.warning("Estrazione interrotta manualmente.")
    except RuntimeError as e:
        logger.error("Errore critico durante l'esecuzione: %s", e, exc_info=True)
    except mysql.connector.Error as e:
        logger.error("Errore di database: %s", e, exc_info=True)


if __name__ == "__main__":  # pragma: no cover
    main()
