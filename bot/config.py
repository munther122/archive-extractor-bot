from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


def _ids(value: str) -> frozenset[int]:
    return frozenset(int(x.strip()) for x in value.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    token: str = os.getenv("BOT_TOKEN", "").strip()
    admin_ids: frozenset[int] = _ids(os.getenv("833001594", ""))
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", str(20 * 1024 * 1024)))
    max_extracted_size: int = int(os.getenv("MAX_EXTRACTED_SIZE", str(200 * 1024 * 1024)))
    max_files: int = int(os.getenv("MAX_FILES", "100"))
    max_concurrent_jobs: int = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
    max_single_output: int = int(os.getenv("MAX_SINGLE_OUTPUT", str(49 * 1024 * 1024)))
    retention_hours: int = int(os.getenv("RETENTION_HOURS", "24"))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "bot.sqlite3"

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
