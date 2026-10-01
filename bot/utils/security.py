from pathlib import Path


def safe_path(root: Path, name: str) -> Path:
    name = name.replace("\\", "/")
    target = (root / name).resolve()
    root = root.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"مسار غير آمن: {name}")
    return target


def reject_symlink(path: Path):
    if path.is_symlink():
        raise ValueError("الروابط الرمزية غير مسموحة")


def validate_limits(count, total, file_size, max_files, max_total, max_single):
    if count > max_files: raise ValueError("تجاوز عدد الملفات الحد المسموح")
    if total > max_total: raise ValueError("تجاوز الحجم بعد الفك الحد المسموح")
    if file_size > max_single: raise ValueError("ملف مفرد أكبر من الحد المسموح")
