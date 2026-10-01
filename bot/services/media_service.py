import asyncio, shutil, tempfile
from pathlib import Path

class MediaService:
    def __init__(self, settings): self.s=settings
    async def convert(self, source: Path, kind: str) -> Path:
        if shutil.which('ffmpeg') is None: raise RuntimeError('FFmpeg غير مثبت في البيئة')
        ext='.mp3' if kind=='audio' else '.mp4'; out=source.with_suffix(ext)
        cmd=['ffmpeg','-y','-i',str(source)]
        cmd += ['-vn','-codec:a','libmp3lame','-q:a','4'] if kind=='audio' else ['-c:v','libx264','-preset','veryfast','-c:a','aac','-movflags','+faststart']
        cmd.append(str(out))
        proc=await asyncio.create_subprocess_exec(*cmd,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
        _,err=await proc.communicate()
        if proc.returncode: raise RuntimeError('فشل تحويل الوسائط')
        return out
