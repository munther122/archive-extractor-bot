import shutil, subprocess, tarfile, zipfile
from pathlib import Path
from bot.utils.security import safe_path, reject_symlink, validate_limits

class ArchiveService:
    def __init__(self, settings): self.s=settings
    def _zip(self, src, out):
        count=total=folders=0
        with zipfile.ZipFile(src) as z:
            for i in z.infolist():
                p=safe_path(out,i.filename)
                if i.is_dir(): p.mkdir(parents=True,exist_ok=True); folders+=1; continue
                validate_limits(count+1,total+i.file_size,i.file_size,self.s.max_files,self.s.max_extracted_size,self.s.max_single_output)
                p.parent.mkdir(parents=True,exist_ok=True)
                with z.open(i) as a,p.open('wb') as b: shutil.copyfileobj(a,b,1024*1024)
                count+=1; total+=i.file_size
        return count,folders,total
    def _tar(self, src, out):
        count=total=folders=0
        with tarfile.open(src,'r:*') as t:
            for m in t.getmembers():
                p=safe_path(out,m.name)
                if m.isdir(): p.mkdir(parents=True,exist_ok=True); folders+=1; continue
                if not m.isfile(): raise ValueError('نوع ملف غير مسموح داخل TAR')
                validate_limits(count+1,total+m.size,m.size,self.s.max_files,self.s.max_extracted_size,self.s.max_single_output)
                p.parent.mkdir(parents=True,exist_ok=True); f=t.extractfile(m)
                if f:
                    with f,p.open('wb') as b: shutil.copyfileobj(f,b,1024*1024)
                count+=1; total+=m.size
        return count,folders,total
    def _external(self, src, out):
        listing=subprocess.run(['7z','l','-slt',str(src)],capture_output=True,text=True,timeout=60)
        if listing.returncode: raise ValueError('تعذر قراءة الأرشيف أو أنه محمي بكلمة مرور')
        count=total=0; current=None; size=0
        for line in listing.stdout.splitlines()+['']:
            if line.startswith('Path = '): current=line[7:]
            elif line.startswith('Size = '):
                try:size=int(line[7:])
                except ValueError:size=0
            elif not line and current is not None:
                if current not in (str(src),'') and not current.endswith('/'):
                    validate_limits(count+1,total+size,size,self.s.max_files,self.s.max_extracted_size,self.s.max_single_output);count+=1;total+=size
                current=None;size=0
        out.mkdir(parents=True,exist_ok=True)
        r=subprocess.run(['7z','x','-y',f'-o{out}',str(src)],capture_output=True,text=True,timeout=300)
        if r.returncode: raise ValueError('تعذر فك الأرشيف')
        for p in out.rglob('*'): reject_symlink(p); safe_path(out,str(p.relative_to(out)))
        files=[p for p in out.rglob('*') if p.is_file()]; dirs=[p for p in out.rglob('*') if p.is_dir()]
        return len(files),len(dirs),sum(p.stat().st_size for p in files)
    def extract(self, src: Path, out: Path):
        out.mkdir(parents=True,exist_ok=True); ext=src.suffix.lower(); suff=[x.lower() for x in src.suffixes]
        if ext=='.zip': return self._zip(src,out)
        if ext in ('.rar','.7z'): return self._external(src,out)
        if any(x in suff for x in ('.tar','.gz','.bz2','.xz')) or src.name.lower().endswith('.tgz'): return self._tar(src,out)
        raise ValueError('الامتداد غير مدعوم')
