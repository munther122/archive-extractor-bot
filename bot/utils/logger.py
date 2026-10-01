import logging

def setup_logging():
    logging.basicConfig(format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',level=logging.INFO)
