import io, tarfile, zipfile
from pathlib import Path
import pytest
from bot.services.archive_service import ArchiveService

class S:
    max_files=10; max_extracted_size=1024*1024; max_single_output=512*1024

def test_zip_arabic_and_nested(tmp_path):
    src=tmp_path/'x.zip'; out=tmp_path/'out'
    with zipfile.ZipFile(src,'w') as z:
        z.writestr('مجلد/ملف.txt','مرحبا')
    assert ArchiveService(S()).extract(src,out)[0]==1
    assert (out/'مجلد'/'ملف.txt').read_text()=='مرحبا'

def test_tar_gz(tmp_path):
    src=tmp_path/'x.tar.gz'; out=tmp_path/'out'; item=tmp_path/'item.txt'; item.write_text('data')
    with tarfile.open(src,'w:gz') as t: t.add(item,arcname='item.txt')
    assert ArchiveService(S()).extract(src,out)[0]==1
    assert (out/'item.txt').read_text()=='data'

def test_zip_slip(tmp_path):
    src=tmp_path/'bad.zip'; out=tmp_path/'out'
    with zipfile.ZipFile(src,'w') as z: z.writestr('../escape.txt','bad')
    with pytest.raises(ValueError): ArchiveService(S()).extract(src,out)
    assert not (tmp_path/'escape.txt').exists()

def test_archive_bomb_limit(tmp_path):
    src=tmp_path/'big.zip'; out=tmp_path/'out'
    with zipfile.ZipFile(src,'w') as z: z.writestr('big.txt','x'*2048)
    class Small:
        max_files=10; max_extracted_size=1024; max_single_output=512*1024
    with pytest.raises(ValueError): ArchiveService(Small()).extract(src,out)
