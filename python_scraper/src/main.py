import argparse
import logging

import mysql.connector
from tqdm import tqdm

from src.api_client import ApiError
from src.scraper import retry_failures, run_scraper


class TqdmLoggingHandler(logging.Handler):
    """Routes log output through tqdm.write() so the progress bar stays pinned."""

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
        except Exception:
            self.handleError(record)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[TqdmLoggingHandler()],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="OPIS Manager Scraper")
    parser.add_argument(
        "--year",
        "-y",
        type=int,
        required=True,
        help="Academic year to scrape (e.g., 2024 for 2024/2025)",
    )
    parser.add_argument(
        "--retry",
        "-r",
        action="store_true",
        help="Retry failed requests from the failures file for the given year",
    )
    args = parser.parse_args()

    logger.info("Inizializzazione Opis Manager Scraper...")

    try:
        if args.retry:
            retry_failures(args.year)
        else:
            run_scraper(args.year)
        logger.info("Estrazione dati completata con successo.")

    except KeyboardInterrupt:
        logger.warning("Estrazione interrotta manualmente.")
    except ApiError as e:
        logger.error("Errore API critico: %s", e, exc_info=True)
    except RuntimeError as e:
        logger.error("Errore critico durante l'esecuzione: %s", e, exc_info=True)
    except mysql.connector.Error as e:
        logger.error("Errore di database: %s", e, exc_info=True)


if __name__ == "__main__":  # pragma: no cover
    main()
